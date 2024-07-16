import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import yt_dlp  # type: ignore

import archie.config as cfg
from archie.utils import utils

from ._filter import filter_video
from .download import finish_progress, progress_hooks, start_progress

# TODO: fix yt-dlp output breaking rich printing


@dataclass
class DownloadedVideo:
    path: Path
    video_relative_path: Path
    format: str


def debug_write_yt(yt, data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(yt.sanitize_info(data)))


def debug_write(data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(data))


class YouTubeAPI:
    in_spider = False

    def _log(self, *args, **kwargs):
        if not self.in_spider:
            utils.module_log("youtube api", "dark_red", *args, **kwargs)
        else:
            utils.module_log("youtube api (spider)", "magenta", *args, **kwargs)

    def get_channel_id_from_url(self, account_link: str) -> str | None:
        res = self.get_channel_and_videos(account_link)
        if not res:
            return None

        channel, videos = res
        return channel["id"]

    def get_channel_url_from_id(self, account_id: str):
        if account_id.startswith("@"):
            raise Exception("bug somewhere which is using @ usernames for yt")

        return f"https://youtube.com/channel/{account_id}"

    def get_channel_and_videos(self, account_id, from_spider: bool = False) -> Tuple[dict, list] | None:
        ydl_opts = {
            "extract_flat": True,  # don't parse individual videos, just get the data available from the /videos page
            "quiet": True,
        }

        channel_link = self.get_channel_url_from_id(account_id)

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            try:
                data = yt.extract_info(
                    f"{channel_link}/videos", download=False
                )  # note: fetching videos page instead of about page since i'm fairly certain (need to re-check) that they return the same data, just with videos also having videos
                data["id"] = data.pop(
                    "channel_id"
                )  # id is wrong and uses @usernames just replace it with channel_id which is proper
                videos = data.pop("entries")
                return data, videos
            except yt_dlp.utils.DownloadError as e:
                if "This channel does not have a videos tab" in e.msg:
                    self._log(f"channel has no videos, fetching about page instead ({channel_link})")
                else:
                    self._log(f"misc parsing error, skipping parsing ({channel_link})")
                    return None

                try:
                    data = yt.extract_info(f"{channel_link}/about", download=False)
                    return data, []
                except yt_dlp.utils.DownloadError as e:
                    if "This channel does not have a about tab" in e.msg:
                        self._log("channel doesn't have an about page? skipping")
                        return None
                    else:
                        raise e

    def get_video_data(self, video_id: str, spider: bool = False) -> Tuple[dict, None] | Tuple[None, yt_dlp.utils.YoutubeDLError]:
        # gets all info and commenters for a video

        ydl_opts = {
            "getcomments": True,
            "quiet": True,
        }

        video_link = f"https://www.youtube.com/watch?v={video_id}"

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            try:
                data = yt.extract_info(video_link, download=False)

                if filter_video(data):
                    # todo: what to do when the video's already been added
                    pass

                return data, None
            except yt_dlp.utils.DownloadError as e:
                return None, e  # idk if this is good way to do this

    def get_channel_playlists(self, account_id):
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,  # don't parse individual playlists
        }

        playlist_link = self.get_channel_url_from_id(account_id) + "/playlists"

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            try:
                data = yt.extract_info(playlist_link, download=False)
            except yt_dlp.utils.DownloadError as e:
                if "This channel does not have a playlists tab" in e.msg:
                    self._log(f"channel {account_id} has no playlists, skipping. ({account_id})")
                    return []
                else:
                    # AH?
                    raise e

            return data["entries"]

    def get_playlist(self, playlist_id: str):
        ydl_opts = {
            "quiet": True,
            "loglevel": "panic",
            "extract_flat": True,  # don't parse individual videos. also get videos that are unavailable
            "external_downloader_args": ["-loglevel", "panic"],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as yt:
            data = yt.extract_info(f"https://www.youtube.com/playlist?list={playlist_id}", download=False)
            videos = data.pop("entries")
            return data, videos

    def download(self, channel: dict, video: dict, download_folder: Path) -> DownloadedVideo | None:
        # returns the downloaded format

        start_progress(channel, video)

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
                lambda: yt.extract_info(f"https://www.youtube.com/watch?v={video['id']}", download=True),
                lambda: self._log(f"failed to download video '{video['title']}', retrying... ({video['id']})"),
                max_retries=max_retries,
            )

            self._log("finished download for", video["title"])
            finish_progress(video)

            if not data:
                self._log(f"download for video '{video['title']}' failed after {max_retries} retries, skipping. ({video['id']})")
                return None

            download_data = data["requested_downloads"][0]

            # get just the download path, not the stuff before it. so c:\...\temp-downloads\channel\video.mkv just becomes channel\video.mkv
            downloaded_path = Path(download_data["filepath"])
            video_relative_path = downloaded_path.relative_to(cfg.TEMP_DL_PATH)

            # build proper download path
            final_path = download_folder / video_relative_path

            if final_path.exists():
                self._log("video already exists? skipping")
            else:
                # move completed download
                final_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(downloaded_path, final_path)

            return DownloadedVideo(
                path=final_path,
                video_relative_path=video_relative_path,
                format=download_data["format_id"],
            )
