import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import archie.database.database as db
from archie.config import Config
from archie.services.base_service import BaseService
from archie.services.youtube.api import YouTubeAPI
from archie.utils import utils


def log(*args, **kwargs):
    utils.module_log("parser (youtube)", "green", *args, **kwargs)


class YouTubeService(BaseService):
    api = YouTubeAPI()

    _download_counter = 0
    _download_counter_lock = threading.Lock()
    _downloads_sleeping = False

    @property
    def get_service_name(self):
        return "YouTube"

    def get_account_url_from_id(self, id: str):
        return self.api.get_channel_url_from_id(id)

    def get_account_id_from_url(self, link: str):
        return self.api.get_channel_id_from_url(link)

    def run(self, config: Config):
        log("Starting")

        self._cleanup(config)

        for i in range(5):
            threading.Thread(target=self._download_videos, args=(config,), daemon=True).start()

        threading.Thread(target=self._parse, args=(config,), daemon=True).start()

    def _cleanup(self, config: Config):
        # remove deleted downloads
        for download in db.ContentDownload.get_downloads():
            path = Path(download.path)

            if not path.exists():
                log(f"download for video {download.video.title} no longer exists, deleting from db")
                download.delete()

        # reset downloading state
        db.YouTubeVideo.reset_download_states()

    def _download_videos(self, config: Config):  # TODO: some of this can be generalised most likely
        while True:
            # TODO: FIX
            # video = db.YouTubeVideo.get_next_download()
            video = None
            if not video:
                with self._download_counter_lock:
                    if self._download_counter == 0:
                        if not self._downloads_sleeping:
                            self._downloads_sleeping = True
                            log("downloaded all videos, sleeping...")

                time.sleep(1)
                continue

            self.downloads_sleeping = False

            assert len(video.channel.archives) > 0  # todo: i know this will fail at some point i have to code the logic for it

            archive_name = video.channel.archives[0].name

            archive_config = None
            for c in config.archives:
                if c.name == archive_name:
                    archive_config = c
                    break

            assert archive_config, f"FATAL ERROR: archive {archive_name} no longer exists."

            log(f"downloading video {video.title} ({video.id})")

            download_path = Path(archive_config.downloads.download_path).expanduser()

            with self._download_counter_lock:
                self._download_counter += 1

            download_data = self.api.download(video, download_path)

            with self._download_counter_lock:
                self._download_counter -= 1

            if not download_data:
                # download somehow failed 5 times, skip it
                # todo: actually skip it, right now it'll just try to download it again
                continue

            for other_config in config.archives[1:]:
                other_download_path = Path(other_config.downloads.download_path).expanduser()

                if other_download_path != download_path:
                    # user wants this channel's videos downloaded to another path as well. copy the video rather than redownloading
                    relative_path = download_data.path.relative_to(download_path)
                    copy_path = other_download_path / relative_path

                    copy_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(download_data.path, copy_path)

                    log(f"copied downloaded video to {other_config.downloads.download_path}")

            video.add_download(download_data.path, download_data.format)

            log(f"finished downloading {video.title} to {download_data.path}, format {download_data.format}")

    def _parse(self, config: Config):  # TODO: some of this can be generalised most likely
        sleeping = False

        while True:
            for archive_config in config.archives:
                # parse all manually added accounts
                for entity in archive_config.entities:
                    for account in entity.accounts:
                        if account.service != self.get_service_name:
                            continue

                        # check if already parsed
                        existing_account = self.api.get_existing_account(account.id)
                        if existing_account:
                            # if account not in archive.channels:
                            #     TODO: add reference
                            #     archive.add_channel(account, False)
                            #     pass

                            continue

                        # new account, parse
                        log("getting channel")
                        channel_data = self.api.get_channel(account.id, db.AccountStatus.ACCEPTED)
                        channel: db.YouTubeAccount = db.YouTubeAccount.create_or_update(
                            status=channel_data["status"],
                            id=channel_data["id"],
                            name=channel_data["name"],
                            avatar_url=channel_data["avatar_url"],
                            banner_url=channel_data["banner_url"],
                            description=channel_data["description"],
                            subscribers=channel_data["subscribers"],
                            tags=channel_data["tags"],
                            verified=channel_data["verified"],
                        )

                        log("getting playlists")
                        channel_playlist_datas = self.api.get_channel_playlists(channel, account.id)
                        if channel_playlist_datas:
                            for channel_playlist_data in channel_playlist_datas:
                                playlist_data = self.api.get_playlist(channel_playlist_data["id"], channel)

                                playlist = channel.add_or_update_playlist(
                                    id=playlist_data["id"],
                                    title=playlist_data["title"],
                                    availability=playlist_data["availability"],
                                    description=playlist_data["description"],
                                    tags_list=playlist_data["tags_list"],
                                    thumbnail_url=playlist_data["thumbnail_url"],
                                    modified_date=playlist_data["modified_date"],
                                    view_count=playlist_data["view_count"],
                                    channel_id=playlist_data["channel_id"],
                                    videos=playlist_data["videos"],
                                )

                                log(f"parsed playlist {playlist.title}, {len(playlist.videos)} videos found ({playlist.id})")

                        for basic_video_data in channel_data["videos"]:
                            log(f"adding/updating video {basic_video_data['title']}")
                            video: db.YouTubeVideo = channel.add_or_update_video(
                                id=basic_video_data["id"],
                                title=basic_video_data["title"],
                                thumbnail_url=basic_video_data["thumbnail_url"],
                                description=basic_video_data["description"],
                                duration=basic_video_data["duration"],
                                availability=basic_video_data["availability"],
                                views=basic_video_data["views"],
                            )

                            if channel.status == db.AccountStatus.ACCEPTED:
                                video_min_update_time = datetime.utcnow() - timedelta(
                                    hours=archive_config.updating.video_update_gap_hours
                                )
                                if not video.fully_parsed or (video.update_time and video.update_time <= video_min_update_time):
                                    log(f"getting video data for {basic_video_data['title']}")
                                    video_data = self.api.get_video_data(basic_video_data["id"])

                                    video.update_details(
                                        thumbnail_url=video_data["thumbnail_url"],
                                        categories_list=video_data["categories_list"],
                                        tags_list=video_data["tags_list"],
                                        availability=video_data["availability"],
                                        timestamp=video_data["timestamp"],
                                    )

                                    if video_data["comments"]:
                                        for comment_data in video_data["comments"]:
                                            log(f"adding comment for {basic_video_data['title']}\n\t{comment_data['text']}")
                                            comment: db.YouTubeVideoComment = video.add_comment(
                                                id=comment_data["id"],
                                                parent_id=comment_data["parent_id"],
                                                text=comment_data["text"],
                                                likes=comment_data["likes"],
                                                channel_id=comment_data["channel_id"],
                                                channel_avatar_url=comment_data["channel_avatar_url"],
                                                timestamp=comment_data["timestamp"],
                                                favorited=comment_data["favorited"],
                                            )

                                            if comment.youtube_account and comment.youtube_account.fully_parsed:
                                                continue

                                            # if spider:
                                            #     # new channel, add to queue
                                            #     global in_spider
                                            #     in_spider = True
                                            #     self.get_account(comment.channel_id, AccountStatus.QUEUED, from_spider=True)
                                            #     in_spider = False

                                    video.set_updated()

                                    # log(f"parsed video details, got {len(video.comments)} comments")

                        channel.set_updated()

                # # parse all accepted accounts (spider or db editing)
                # while True:
                #     before_time = datetime.utcnow() - timedelta(hours=archive_config.updating.channel_update_gap_hours)
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
