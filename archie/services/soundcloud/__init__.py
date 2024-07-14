import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Set

from soundcloud import SoundCloud

from archie.config import Config
from archie.services.base_download import copy_download
from archie.services.base_service import BaseService
from archie.utils import utils

from . import database as db
from .download import download_track

sc = SoundCloud()

# TODO: a lot of this is the same as youtube, figure out how to generalise
# TODO: multithreaded parsing? generalise thread locks? i don't think there's a rate limit?


def log(*args, **kwargs):
    utils.module_log("soundcloud", "orange3", *args, **kwargs)


class SoundCloudService(BaseService):
    _current_downloads: Set[int] = set()
    _current_downloads_lock = threading.Lock()

    @property
    def service_name(self):
        return "SoundCloud"

    def get_account_url_from_id(self, id: str):
        user = sc.get_user(id)
        return user.permalink_url if user else None

    def get_account_id_from_url(self, link: str):
        # TODO: i don't like this at all but it seems to work? if it doesn't then change how this stuff works
        username = link.split("soundcloud.com/")[-1].split("/")[0]
        user = sc.get_user_by_username(username)
        return user.id

    def run(self, config: Config):
        log("starting")

        threading.Thread(target=self._background, daemon=True).start()

        threading.Thread(target=self._check_downloads, args=(config,), daemon=True).start()

        for i in range(5):
            threading.Thread(target=self._download_tracks, args=(config,), daemon=True).start()

        threading.Thread(target=self._parse, args=(config,), daemon=True).start()

    def _background(self):
        while True:
            db.update_indexes()
            time.sleep(10)

    def __parse_users(self, config: Config):
        for account, entity, archive in config.get_accounts(self.service_name):
            user_min_update_time = datetime.now(timezone.utc) - timedelta(hours=archive.services.soundcloud.user_update_gap_hours)

            db_user = db.get_user(account.id)
            if db_user:
                if db_user["_scan_source"] == "full" and db_user["_scan_time"] > user_min_update_time:
                    continue

                log(f"updating user {db_user['user']['username']} ({account.id})")
            else:
                log(f"parsing user ({account.id})")

            user = sc.get_user(account.id)

            tracks = list(sc.get_user_tracks(user.id, limit=80000))
            playlists = list(sc.get_user_playlists(user.id, limit=80000))
            links = sc.get_user_links(user.id)
            reposts = list(sc.get_user_reposts(user.id, limit=80000))

            db.store_user(user, "full", "accepted", tracks, playlists, links, reposts)
            log(f"parsed user {user.username} ({user.id})")

    def __parse_tracks(self, config: Config):
        for account, entity, archive in config.get_accounts(self.service_name):
            user = db.get_user(account.id)
            if not user:
                continue

            track_min_update_time = datetime.now(timezone.utc) - timedelta(
                hours=archive.services.soundcloud.track_update_gap_hours
            )

            for i, track_id in enumerate(user["tracks"]):
                db_track = db.get_track(track_id)  # TODO: this might be super inefficient, see if u can just get meta

                if db_track:
                    if db_track["_scan_source"] == "full" and db_track["_scan_time"] > track_min_update_time:
                        continue

                    log(f"({i+1}/{len(user['tracks'])}) updating track id {track_id}")
                else:
                    log(f"({i+1}/{len(user['tracks'])}) parsing track id {track_id}")

                track = sc.get_track(track_id)

                log(f"parsing albums | {track.user.username} - {track.title} ({track_id})")
                albums = list(sc.get_track_albums(track_id, limit=80000))

                log(f"parsing comments | {track.user.username} - {track.title} ({track_id})")
                comments = list(sc.get_track_comments(track_id, limit=80000))

                log(f"parsing likers | {track.user.username} - {track.title} ({track_id})")
                likers = list(sc.get_track_likers(track_id, limit=80000))

                log(f"parsing reposters | {track.user.username} - {track.title} ({track_id})")
                reposters = list(sc.get_track_reposters(track_id, limit=80000))

                log(f"parsing playlists | {track.user.username} - {track.title} ({track_id})")
                playlists = list(sc.get_track_playlists(track_id, limit=80000))

                db.store_track(track, "full", albums, comments, likers, reposters, playlists)
                log(f"parsed {track.user.username} - {track.title} ({track_id})")

    def _parse(self, config: Config):
        while True:
            self.__parse_users(config)
            self.__parse_tracks(config)

            time.sleep(1)

    def _check_downloads(self, config: Config):
        for download in db.get_downloads():
            if not download:
                continue

            track_id = download["track_id"]
            path = Path(download["path"])

            # remove deleted downloads
            if not path.exists():
                log(f"download for video '{track_id}' no longer exists, deleting from db")
                db.remove_download(download["_id"])
                continue

            # check if the video exists everywhere it should
            track = db.get_track(track_id)
            if not track:
                log(f"note: download {track_id} has no track in database")
                continue

            user = db.get_user(track["track"]["user_id"])
            if not user:
                log(f"note: download {track_id} has no user in database")
                continue

            track_archives = list(config.find_archives_with_account(self.service_name, user["user"]["id"]))

            for archive in track_archives:
                copy_download(self.service_name, path, download["relative_video_path"], archive)

    def _download_tracks(self, config: Config):  # TODO: some of this can be generalised most likely
        while True:
            with self._current_downloads_lock:  # todo should this be looping over archives first idk
                start = time.time()
                track = db.get_undownloaded_track(list(self._current_downloads))
                execution_time_secs = time.time() - start

                if execution_time_secs > 1:
                    # TODO: check this
                    log(f"took {execution_time_secs} secs to find an undownloaded track, debug & optimise")

                if track:
                    self._current_downloads.add(track["track"]["id"])

            if not track:
                time.sleep(1)
                continue

            # this isn't needed, but nice for printing TODO: maybe remove
            user = db.get_user(track["track"]["user_id"])
            assert user, "User does not exist?"

            user_archives = list(config.find_archives_with_account(self.service_name, user["user"]["id"]))

            assert len(user_archives) > 0  # todo: i know this will fail at some point i have to code the logic for it

            archive = user_archives[0]

            log(f"downloading track {user['user']['username']} - {track['track']['title']} ({track['track']['id']})")

            download_path = Path(archive.downloads.download_path).expanduser() / self.service_name

            # hate this but its cause internally scdl needs proper types. TODO: figure out workaround
            sc_user = sc.get_user(user["user"]["id"])
            sc_track = sc.get_track(track["track"]["id"])

            download_data = download_track(sc_user, sc_track, download_path)

            with self._current_downloads_lock:
                self._current_downloads.remove(track["track"]["id"])

            if not download_data:
                # download somehow failed 5 times, skip it
                # todo: actually skip it, right now it'll just try to download it again
                continue

            db.store_download(
                track["track"]["id"],
                download_data.path,
                download_data.video_relative_path,
                download_data.wave,
            )

            for other_archive in user_archives[1:]:
                copy_download(self.service_name, download_data.path, download_data.video_relative_path, other_archive)

            log(f"finished downloading {track['track']['title']} (wave {download_data.wave})")
