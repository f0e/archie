import threading
import time

from ..sources import youtube, wayback
from ..database.database import Video
from ..utils.config import settings


def log(*args, **kwargs):
    print("[downloader] " + " ".join(map(str, args)), **kwargs)


def download_videos():
    sleeping = False

    while True:
        video = Video.get_next_download()
        if not video:
            if not sleeping:
                log("downloaded all videos, sleeping...")
                sleeping = True

            time.sleep(5000)
            break

        download_data = youtube.download_video(video, settings.download_path)

        video.add_download(download_data["path"], download_data["format"])

        log(f"finished downloading {video.title} to {download_data['path']}, format {download_data['format']}")


def run():
    # threading.Thread(target=download_videos).start()
    download_videos()
