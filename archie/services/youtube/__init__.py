import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Set

from archie.config import ArchiveConfig, Config
from archie.services.base_service import BaseService
from archie.services.youtube.api import YouTubeAPI
from archie.utils import utils

from . import database as db


def log(*args, **kwargs):
    utils.module_log("parser (youtube)", "green", *args, **kwargs)


class YouTubeService(BaseService):
    api = YouTubeAPI()

    _downloads_sleeping = False
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
        log("Starting")

        threading.Thread(target=self._cleanup, daemon=True).start()

        for i in range(5):
            threading.Thread(target=self._download_videos, args=(config,), daemon=True).start()

        threading.Thread(target=self._parse, args=(config,), daemon=True).start()

    def _cleanup(self):
        log("starting download cleanup")

        # remove deleted downloads
        for video_id, download in db.get_downloads():
            path = Path(download["path"])

            if not path.exists():
                log(f"download for video '{video_id}' no longer exists, deleting from db")
                db.remove_download(video_id)

        log("finished cleaning up downloads")

    def _download_videos(self, config: Config):  # TODO: some of this can be generalised most likely
        while True:
            with self._current_downloads_lock:
                video = db.get_undownloaded_video(list(self._current_downloads))
                # TODO: threads clash
                if not video:
                    if len(self._current_downloads) == 0:
                        if not self._downloads_sleeping:
                            self._downloads_sleeping = True
                            log("downloaded all videos, sleeping...")

                    time.sleep(1)
                    continue

                video_data = video["video"]
                self._current_downloads.add(video_data["id"])

            channel = db.get_channel(video_data["channel_id"])
            assert channel, "Channel does not exist?"

            channel_data = channel["channel"]

            self.downloads_sleeping = False

            video_archives: list[ArchiveConfig] = []
            for archive in config.archives:  # awesome
                for entity in archive.entities:
                    for account in entity.accounts:
                        if account.service == self.service_name and account.id == channel_data["id"]:
                            video_archives.append(archive)

            assert len(video_archives) > 0  # todo: i know this will fail at some point i have to code the logic for it
            assert len(video_archives) == 1, "fix"

            archive = video_archives[0]

            log(f"downloading video {video_data['title']} ({video_data['id']})")

            download_path = Path(archive.downloads.download_path).expanduser()

            download_data = self.api.download(channel_data, video_data, download_path)

            with self._current_downloads_lock:
                self._current_downloads.remove(video_data["id"])

            if not download_data:
                # download somehow failed 5 times, skip it
                # todo: actually skip it, right now it'll just try to download it again
                continue

            # todo: reimplement with the array above
            # for other_config in config.archives[1:]:
            #     other_download_path = Path(other_config.downloads.download_path).expanduser()

            #     if other_download_path != download_path:
            #         # user wants this channel's videos downloaded to another path as well. copy the video rather than redownloading
            #         relative_path = download_data.path.relative_to(download_path)
            #         copy_path = other_download_path / relative_path

            #         copy_path.parent.mkdir(parents=True, exist_ok=True)
            #         shutil.copy(download_data.path, copy_path)

            #         log(f"copied downloaded video to {other_config.downloads.download_path}")

            db.store_download(video_data["id"], download_data.path, download_data.format)

            log(f"finished downloading {video_data['title']} to {download_data.path}, format {download_data.format}")

    def _parse(self, config: Config):  # TODO: some of this can be generalised most likely
        sleeping = False

        while True:
            for archive_config in config.archives:
                # parse all manually added accounts
                for entity in archive_config.entities:
                    for account in entity.accounts:
                        if account.service != self.service_name:
                            continue

                        # todo: check status accepted here

                        # check if already parsed
                        existing_account = db.get_channel(account.id)
                        if existing_account:
                            # log("already added channel", account.id)
                            # if account not in archive.channels:
                            #     TODO: add reference
                            #     archive.add_channel(account, False)
                            #     pass

                            continue

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

                        for basic_video_data in channel_videos:
                            video_min_update_time = datetime.now(timezone.utc) - timedelta(
                                hours=archive_config.updating.video_update_gap_hours
                            )

                            video = db.get_video(basic_video_data["id"])
                            video_scan_time = datetime.fromisoformat(video["meta"]["scan_time"]) if video else None

                            if not video or (video_scan_time and video_scan_time <= video_min_update_time):
                                log(f"getting video data for {basic_video_data['title']}")
                                video = self.api.get_video_data(basic_video_data["id"])
                                db.store_video(video)

                                if "comments" in video:
                                    log(f"parsed video details, got {len(video['comments'])} comments")
                                else:
                                    log("parsed video details, got no comments")

                        account.update_time = datetime.now(timezone.utc)
                        config.save()

                # # parse all accepted accounts (spider or db editing)
                # while True:
                #     before_time = datetime.now(timezone.utc) - timedelta(hours=archive_config.updating.channel_update_gap_hours)
                #     account = archive.get_next_youtube_account_of_status(db.AccountStatus.ACCEPTED, before_time)
                #     if not account:
                #         break

                #     log(f"updating channel {account.name} ({account.id})")

                #     self.services.get_account(account.id, archive_config, account.status)

                #     log(f"finished parsing {account.name} ({account.id})")

                if not sleeping:
                    log("finished parsing accepted channels, sleeping...")
                    sleeping = True

                time.sleep(1)
