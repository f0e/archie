import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yt_dlp  # type: ignore

import archie.config as cfg
from archie.database.database import (
    AccountStatus,
    YouTubeAccount,
    YouTubePlaylist,
    YouTubeVideo,
)
from archie.utils import utils

from ._filter import filter_video
from .download import finish_progress, progress_hooks, start_progress


@dataclass
class DownloadedVideo:
    path: Path
    format: str


def debug_write_yt(yt, data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(yt.sanitize_info(data)))


def debug_write(data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(data))


def log(in_spider, *args, **kwargs):
    if not in_spider:
        utils.module_log("youtube", "red", *args, **kwargs)
    else:
        utils.module_log("youtube (spider)", "magenta", *args, **kwargs)


class YouTubeAPI:
    in_spider = False

    def _log(self, *args, **kwargs):
        log(self.in_spider, *args, **kwargs)

    def get_channel_id_from_url(self, account_link: str) -> str | None:
        ydl_opts = {
            "extract_flat": True,  # don't parse individual videos, just get the data available from the /videos page
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            try:
                data = yt.extract_info(account_link, download=False, process=False)
                return data["id"]
            except Exception as e:  # TODO: get actual exception type and handle other errors differently?
                self._log("Failed to get account id from url '{account_link}'")
                self._log(e)
                return None

    def get_channel_url_from_id(self, account_id: str):
        return f"https://youtube.com/channel/{account_id}"

    def get_channel(self, account_id: str, status: AccountStatus, from_spider: bool = False):
        ydl_opts = {
            "extract_flat": True,  # don't parse individual videos, just get the data available from the /videos page
            "quiet": True,
        }

        channel_link = self.get_channel_url_from_id(account_id)

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            try:
                data = yt.extract_info(f"{channel_link}/videos", download=False)
            except yt_dlp.utils.DownloadError as e:
                if "This channel does not have a videos tab" in e.msg:
                    self._log(f"channel has no videos, fetching about page instead ({channel_link})")
                else:
                    self._log(f"misc parsing error, skipping parsing ({channel_link})")
                    return None

                try:
                    data = yt.extract_info(f"{channel_link}/about", download=False)
                except yt_dlp.utils.DownloadError as e:
                    if "This channel does not have a about tab" in e.msg:
                        self._log("channel doesn't have an about page? skipping")
                        return None
                    else:
                        raise e

            # get avatar and banner
            avatar_url = None
            banner_url = None
            for image in data["thumbnails"]:
                if image["id"] == "avatar_uncropped":
                    avatar_url = image["url"]
                elif image["id"] == "banner_uncropped":
                    banner_url = image["url"]

            verified = False
            if "channel_is_verified" in data:
                verified = data["channel_is_verified"]

            subscribers = data["channel_follower_count"] or 0

            # num_videos = len(data["entries"])

            # if from_spider:
            #     if filter_spider_channel(archive_config.spider.filters, subscribers, verified, num_videos):
            #         # todo: what to do when the channel's already been added?
            #         # todo: store filtered channels in db so they don't get checked again? and it'll also store their
            #         #       info in case you change your mind on filter settings?
            #         # todo: go back to parsing /about for filtering???
            #         self._log("filtered channel")
            #         return None

            return {
                "status": status,
                "id": data["channel_id"],
                "name": data["channel"],
                "avatar_url": avatar_url,
                "banner_url": banner_url,
                "description": data["description"],
                "subscribers": subscribers,
                "tags": ",".join(data["tags"]),
                "verified": verified,
                "videos": [
                    {
                        "id": video["id"],
                        "title": video["title"],
                        "thumbnail_url": video["thumbnails"][0][
                            "url"
                        ],  # placeholder, get better quality thumbnail in get_content_data
                        "description": video["description"],
                        "duration": video["duration"],
                        "availability": video["availability"],
                        "views": video["view_count"],
                    }
                    for video in data["entries"]
                ],
            }

    def get_video_data(self, video_id: str, spider: bool = False):
        # gets all info and commenters for a video

        ydl_opts = {
            # "getcomments": True,
            "quiet": True,
        }

        video_link = f"https://www.youtube.com/watch?v={video_id}"

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            data = yt.extract_info(video_link, download=False)

            if filter_video(data):
                # todo: what to do when the video's already been added
                pass

            return {
                "thumbnail_url": data["thumbnail"],
                "categories_list": data["categories"],
                "tags_list": data["tags"],
                "availability": data["availability"],
                "timestamp": datetime.utcfromtimestamp(data["epoch"]),
                "comments": (
                    [
                        {
                            "id": comment["id"],
                            "parent_id": comment["parent"] if comment["parent"] != "root" else None,
                            "text": comment["text"],
                            "likes": comment["like_count"] or 0,
                            "channel_id": comment["author_id"],
                            "channel_avatar_url": comment["author_thumbnail"],
                            "timestamp": comment.utcfromtimestamp(comment["timestamp"]),
                            "favorited": comment["is_favorited"],
                        }
                        for comment in data["comments"]
                    ]
                    if "comments" in data
                    else []
                ),
            }

    def get_channel_playlists(self, channel: YouTubeAccount, account_id: str) -> list[YouTubePlaylist] | None:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,  # don't parse individual playlists
        }

        playlist_link = f"https://www.youtube.com/{account_id}/playlists"

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            try:
                data = yt.extract_info(playlist_link, download=False)
            except yt_dlp.utils.DownloadError as e:
                if "HTTP Error 404: Not Found" in e.msg:
                    self._log(f"channel {account_id} has no playlists, skipping. ({account_id})")
                    return None
                else:
                    # AH?
                    raise e

            playlists = data["entries"]
            print("poopoo", playlists[0])

            return playlists

    def get_playlist(self, playlist_id: str, channel: YouTubeAccount) -> YouTubePlaylist:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,  # don't parse individual videos. also get videos that are unavailable
        }

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            data = yt.extract_info(f"https://www.youtube.com/playlist?list={playlist_id}", download=False)

            return channel.add_or_update_playlist(
                id=data["id"],
                title=data["title"],
                availability=data["availability"],
                description=data["description"],
                tags_list=data["tags"],
                thumbnail_url=data["thumbnails"][0]["url"],
                modified_date=data["modified_date"],
                view_count=data["view_count"],
                channel_id=channel.id,
                videos=data["entries"],
            )

    def download(self, content: YouTubeVideo, download_folder: Path) -> DownloadedVideo | None:
        # returns the downloaded format

        start_progress(content)

        ydl_opts = {
            "progress_hooks": [progress_hooks],
            "quiet": True,
            "noprogress": True,
            # don't redownload videos
            "nooverwrites": True,
            # bypass geographic restrictions
            "geo_bypass": True,
            # write mkv files (prevent webm warning, it just uses mkv anyway)
            "merge_output_format": "mkv",
            # don't download livestreams
            # 'match_filter': '!is_live',
            "writethumbnail": True,
            "format": "bv*+ba",
            "postprocessors": [
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": False,
                },
            ],
            # output folder
            "outtmpl": str(cfg.TEMP_DL_PATH.expanduser() / "%(channel_id)s/%(id)s.f%(format_id)s.%(ext)s"),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            max_retries = 5
            data = utils.retryable(
                lambda: yt.extract_info(f"https://www.youtube.com/watch?v={content.id}", download=True),
                f"failed to download video '{content.title}', retrying... ({content.id})",
                max_retries=max_retries,
            )

            finish_progress(content)

            if not data:
                self._log(f"download for video '{content.title}' failed after {max_retries} retries, skipping. ({content.id})")
                return None

            download_data = data["requested_downloads"][0]

            # get just the download path, not the stuff before it. so c:\...\temp-downloads\channel\video.mkv just becomes channel\video.mkv
            downloaded_path = Path(download_data["filepath"])
            relative_path = downloaded_path.relative_to(cfg.TEMP_DL_PATH)

            # build proper download path
            final_path = download_folder / relative_path

            if final_path.exists():
                self._log("video already exists? skipping")
            else:
                # move completed download
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(downloaded_path, final_path)

            return DownloadedVideo(
                path=final_path,
                format=download_data["format_id"],
            )

    def get_existing_account(self, account_id: str):
        return YouTubeAccount.get(account_id, True)
