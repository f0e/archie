import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Set

from archie.config import Account, Config
from archie.services.base_download import copy_download
from archie.services.base_service import BaseService
from archie.services.youtube.api import YouTubeAPI
from archie.utils import utils

from . import database as db


def log(*args, **kwargs):
    utils.module_log("youtube", "red", *args, **kwargs)


class YouTubeService(BaseService):
    api = YouTubeAPI()

    _current_downloads: Set[str] = set()
    _current_downloads_lock = threading.Lock()

    @property
    def service_name(self):
        return "YouTube"

    def get_account_url_from_id(self, id: str):
        return self.api.get_channel_url_from_id(id)

    def get_account_id_from_url(self, link: str):
        return self.api.get_channel_id_from_url(link)

    def run(self, config: Config):
        log("starting")

        threading.Thread(target=self._check_downloads, args=(config,), daemon=True).start()

        for i in range(5):
            threading.Thread(target=self._download_videos, args=(config,), daemon=True).start()

        threading.Thread(target=self._parse, args=(config,), daemon=True).start()

    def _check_downloads(self, config: Config):
        for video_id, download in db.get_downloads():
            path = Path(download["path"])

            # remove deleted downloads
            if not path.exists():
                log(f"download for video '{video_id}' no longer exists, deleting from db")
                db.remove_download(video_id)
                continue

            # check if the video exists everywhere it should
            video = db.get_video(video_id)
            channel = db.get_channel(video["video"]["channel_id"])
            video_archives = list(config.find_archives_with_account(self.service_name, channel["channel"]["id"]))

            for archive in video_archives:
                copy_download(self.service_name, path, download["relative_video_path"], archive)

    def _download_videos(self, config: Config):  # TODO: some of this can be generalised most likely
        while True:
            with self._current_downloads_lock:  # todo should this be looping over archives first idk
                video = db.get_undownloaded_video(list(self._current_downloads))

                if video:
                    video_data = video["video"]
                    self._current_downloads.add(video_data["id"])
                    log(f"added {video_data['id']} to set")

            if not video:
                time.sleep(1)
                continue

            channel = db.get_channel(video_data["channel_id"])
            assert channel, "Channel does not exist?"

            channel_data = channel["channel"]

            video_archives = list(config.find_archives_with_account(self.service_name, channel_data["id"]))

            assert len(video_archives) > 0  # todo: i know this will fail at some point i have to code the logic for it

            archive = video_archives[0]

            log(f"downloading video {video_data['title']} ({video_data['id']})")

            download_path = Path(archive.downloads.download_path).expanduser() / self.service_name

            downloaded_video_data = self.api.download(channel_data, video_data, download_path)

            with self._current_downloads_lock:
                self._current_downloads.remove(video_data["id"])
                log(f"removed {video_data['id']} from set")

            if not downloaded_video_data:
                # download somehow failed 5 times, skip it
                # todo: actually skip it, right now it'll just try to download it again
                continue

            db.store_download(
                video_data["id"],
                downloaded_video_data.path,
                downloaded_video_data.video_relative_path,
                downloaded_video_data.format,
            )

            for other_archive in video_archives[1:]:
                copy_download(
                    self.service_name, downloaded_video_data.path, downloaded_video_data.video_relative_path, other_archive
                )

            log(f"finished downloading {video_data['title']} (format {downloaded_video_data.format})")

    def __parse_account(self, account: Account):
        # new account, parse
        log("getting channel", account.id)

        res = self.api.get_channel(account.id)
        if res is None:
            raise Exception("Failed to parse channel. TODO: just silently log")

        channel, channel_videos = res
        channel_playlists = self.api.get_channel_playlists(account.id)

        db.store_channel(channel, channel_videos, channel_playlists, "full", "accepted")

        for channel_playlist_data in channel_playlists:
            if db.get_playlist(channel_playlist_data["id"]):
                log("already added playlist", account.id)
                continue

            playlist, videos = self.api.get_playlist(channel_playlist_data["id"])

            db.store_playlist(playlist, videos, "full", "queued")

    def __parse_channels(self, config: Config):  # TODO: some of this can be generalised most likely
        for account, entity, archive in config.get_accounts(self.service_name):
            channel_min_update_time = datetime.now(timezone.utc) - timedelta(
                hours=archive.services.youtube.channel_update_gap_hours
            )

            # todo: check status accepted here

            # check if already parsed
            channel = db.get_channel(account.id)
            if channel:
                channel_scan_time = datetime.fromisoformat(channel["meta"]["scan_time"])
                if channel_scan_time > channel_min_update_time:
                    continue

                log(f"updating channel {channel['channel']['title']} ({account.id})")
            else:
                log(f"parsing channel ({account.id})")

            self.__parse_account(account)

    def __parse_videos(self, config: Config):
        for account, entity, archive in config.get_accounts(self.service_name):
            channel = db.get_channel(account.id)
            if not channel:
                continue

            video_min_update_time = datetime.now(timezone.utc) - timedelta(hours=archive.services.youtube.video_update_gap_hours)

            for basic_video_data in channel["videos"]:
                video = db.get_video(basic_video_data["id"])

                if video:
                    video_scan_time = datetime.fromisoformat(video["meta"]["scan_time"])
                    if video_scan_time > video_min_update_time:
                        continue

                    log(f"updating video '{video['video']['title']}' ({basic_video_data['id']})")
                else:
                    log(f"parsing video ({basic_video_data['id']})")

                log(f"getting video data for {basic_video_data['title']}")

                video = self.api.get_video_data(basic_video_data["id"])
                db.store_video(video)

                if "comments" in video:
                    log(f"parsed video details, got {len(video['comments'])} comments")
                else:
                    log("parsed video details, got no comments")

    def _parse(self, config: Config):
        while True:
            self.__parse_channels(config)
            self.__parse_videos(config)

            time.sleep(1)
