import shutil
import threading
import time
from pathlib import Path

import archie.database.database as db
import archie.sources.youtube as youtube
import archie.utils.utils as utils
from archie.config import TEMP_DL_PATH, Config


def log(*args, **kwargs):
    utils.module_log("downloader", "blue", *args, **kwargs)


def init():
    # remove deleted downloads
    for download in db.VideoDownload.get_downloads():
        path = Path(download.path)

        if not path.exists():
            log(f"download for video {download.video.title} no longer exists, deleting from db")
            download.delete()

    # reset downloading state
    db.Video.reset_download_states()

    # remove temp downloads (for safety, resuming causes issues sometimes)
    shutil.rmtree(TEMP_DL_PATH)


download_counter = 0
download_counter_lock = threading.Lock()
downloads_sleeping = False


def download_videos(config: Config):
    global download_counter, downloads_sleeping

    while True:
        video = db.Video.get_next_download()
        if not video:
            with download_counter_lock:
                if download_counter == 0:
                    if not downloads_sleeping:
                        downloads_sleeping = True
                        log("downloaded all videos, sleeping...")

            time.sleep(1)
            continue

        downloads_sleeping = False

        assert len(video.channel.archives) > 0  # todo: i know this will fail at some point i have to code the logic for it

        archive_name = video.channel.archives[0].name

        archive_config = None
        for c in config.archives:
            if c.name == archive_name:
                archive_config = c
                break

        assert archive_config

        log(f"downloading video {video.title} ({video.id})")

        download_path = Path(archive_config.downloads.download_path).expanduser()

        with download_counter_lock:
            download_counter += 1

        download_data = youtube.download_video(video, download_path)

        with download_counter_lock:
            download_counter -= 1

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
