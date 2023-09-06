import time
from pathlib import Path

from archie.database.database import Video
from archie.sources import youtube
from archie.utils import utils


def log(*args, **kwargs):
    utils.safe_log("downloader", "blue", *args, **kwargs)


def download_videos():
    sleeping = False

    download_path = Path("./downloads-TEMP").expanduser()

    while True:
        video = Video.get_next_download()
        if not video:
            if not sleeping:
                log("downloaded all videos, sleeping...")
                sleeping = True

            time.sleep(1)
            continue

        download_data = youtube.download_video(video, download_path)

        video.add_download(download_data["path"], download_data["format"])

        log(f"finished downloading {video.title} to {download_data['path']}, format {download_data['format']}")
