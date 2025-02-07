import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Set, cast

from archie.config import Config
from archie.services.base_download import copy_download
from archie.services.base_service import BaseService
from archie.services.youtube.api import YouTubeAPI
from archie.utils import utils

from . import database as db

# TODO: check if downloaded videos arent added in archive anymore and delete/move
# TODO: consistency around logging - e.g. apostrophes around names


def log(*args, **kwargs):
    utils.module_log("youtube", "red", *args, **kwargs)


class YouTubeService(BaseService):
    api = YouTubeAPI()

    _current_downloads: Set[str] = set()
    _current_downloads_lock = threading.Lock()
    _fail_list: Set[str] = set()

    @property
    def service_name(self):
        return "YouTube"

    def get_account_url_from_id(self, id: str):
        return self.api.get_channel_url_from_id(id)

    def get_account_id_from_url(self, link: str):
        return self.api.get_channel_id_from_url(link)

    def run(self, config: Config):
        threading.Thread(target=self._background, daemon=True).start()
        threading.Thread(target=self._check_downloads, args=(config,), daemon=True).start()
        threading.Thread(target=self._parse, args=(config,), daemon=True).start()

        for i in range(5):
            threading.Thread(target=self._download_videos, args=(config,), daemon=True).start()

    def _background(self):
        while True:
            db.update_indexes()
            time.sleep(10)

    def _check_downloads(self, config: Config):
        for download in db.get_downloads():
            video_id = download["video_id"]
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
            with self._current_downloads_lock:  # TODO: should this be looping over archives first idk
                video = db.get_undownloaded_video(list(self._current_downloads.union(self._fail_list)))

                if video:
                    video_data = video["video"]
                    self._current_downloads.add(video_data["id"])

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

            if not downloaded_video_data:
                # download somehow failed 5 times, skip it
                self._fail_list.add(video_data["id"])
                # todo: actually skip it properly
                continue

            db.store_download(
                video_data["id"],
                downloaded_video_data.path,
                downloaded_video_data.video_relative_path,
                downloaded_video_data.format,
            )

            for other_archive in video_archives[1:]:
                copy_download(
                    self.service_name,
                    downloaded_video_data.path,
                    downloaded_video_data.video_relative_path,
                    other_archive,
                )

            log(f"finished downloading {video_data['title']} (format {downloaded_video_data.format})")

    def __parse_channels(self, config: Config):  # TODO: some of this can be generalised most likely
        channel_min_update_time = datetime.now(timezone.utc) - timedelta(hours=config.services.youtube.channel_update_gap_hours)

        for account, entity, archive in config.get_accounts(self.service_name):
            # todo: check status accepted here

            # check if already parsed
            db_channel = db.get_channel(cast(str, account.id))
            if db_channel:
                # TODO: move this stuff into aggregation?
                if db_channel["_scan_source"] == "full" and db_channel["_scan_time"] > channel_min_update_time:
                    continue

                log(f"updating channel {db_channel['channel']['channel']} ({account.id})")
            else:
                log(f"parsing channel ({account.id})")

            res = self.api.get_channel_and_videos(account.id)
            if res is None:
                # failed to parse channel, probably deleted or something TODO: more handling
                continue

            channel, channel_videos = res
            channel_playlists = self.api.get_channel_playlists(account.id)

            for video in channel_videos:  # videos don't have it anymore? bandaid fix todo: look into this
                video["channel_id"] = channel["id"]

            db.store_channel(channel, channel_videos, channel_playlists, "full", "accepted")

            log(f"parsed channel {channel['channel']} ({account.id})")

    def __parse_playlists(self, config: Config):
        playlist_min_update_time = datetime.now(timezone.utc) - timedelta(hours=config.services.youtube.playlist_update_gap_hours)

        for db_playlist in db.get_playlist_to_parse(playlist_min_update_time):
            log(f"parsing playlist ({db_playlist['playlist']['id']})")

            # TODO: just parse the first page of the playlist to get the "Last updated" date, and check that to see if it's worth parsing the whole thing. if no videos were added/removed then no point. unless videos were made unprivate..
            playlist, videos = self.api.get_playlist(db_playlist["playlist"]["id"])

            db.store_playlist(playlist, videos, "full", "queued")

            log(f"parsed playlist {playlist['title']} - {len(videos)} videos ({playlist['id']})")

    def __parse_videos(self, config: Config):
        video_min_update_time = datetime.now(timezone.utc) - timedelta(hours=config.services.youtube.video_update_gap_hours)

        for db_video in db.get_video_to_parse(video_min_update_time):
            log(f"parsing video ({db_video['video']['id']})")

            video, error = self.api.get_video_data(db_video["video"]["id"])
            if not video and error:
                # failed to dl, edge case, store it in db
                db.store_video_error(db_video["video"]["id"], error)
                continue

            assert video  # Dumb mypy

            db.store_video(video, "full")

            log(f"parsed video {video['title']} ({video['id']})")

    def _parse(self, config: Config):
        while True:
            self.__parse_channels(config)
            self.__parse_playlists(config)
            self.__parse_videos(config)

            time.sleep(1)
