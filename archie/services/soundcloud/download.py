import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import soundcloud
from rich.progress import TaskID
from scdl import scdl

import archie.config as cfg
import archie.services.soundcloud as sc  # love circular import
from archie.utils import utils

from ..base_download import rich_progress

scdl.logger.propagate = False  # Shut up
logger = logging.getLogger("rich")


def log(self, *args, **kwargs):
    utils.module_log("soundcloud downloads", "dark_orange3", *args, **kwargs)


@dataclass
class DownloadedTrack:
    path: Path
    video_relative_path: Path
    wave: str


def download_track(user: soundcloud.User, track: soundcloud.BasicTrack, download_folder: Path) -> DownloadedTrack | None:
    start_progress(user, track)

    try:
        wave_id = track.waveform_url.split(".com/")[-1].split(".json")[0]

        if not track.media.transcodings:
            raise Exception(f"Track {track.permalink_url} has no transcodings available")

        logger.debug(f"Transcodings: {track.media.transcodings}")

        transcodings = [t for t in track.media.transcodings if t.format.protocol == "hls"]

        # ordered in terms of preference best -> worst
        valid_presets = [("aac", ".m4a"), ("opus", ".opus"), ("mp3", ".mp3")]

        transcoding = None
        ext = None
        for preset_name, preset_ext in valid_presets:
            for t in transcodings:
                if t.preset.startswith(preset_name):
                    transcoding = t
                    ext = preset_ext
            if transcoding:
                break
        else:
            raise Exception(
                "Could not find valid transcoding. Available transcodings: "
                f"{[t.preset for t in track.media.transcodings if t.format.protocol == 'hls']}",
            )

        relative_path = str(user.id) / Path(f"{track.id}.{wave_id}{ext}")
        temp_track_path = cfg.TEMP_DL_PATH / relative_path

        # TODO: check if already downloaded?

        args = scdl.SCDLArgs(opus=True, original_metadata=True, hide_progress=True, name_format="-")

        # Get the requests stream
        url = scdl.get_transcoding_m3u8(sc.sc, transcoding, args)

        encoded = scdl.re_encode_to_buffer(
            track,
            url,
            preset_name if preset_name != "aac" else "ipod",  # We are encoding aac files to m4a, so an ipod codec is used
            True,  # no need to fully re-encode the whole hls stream
            args,
        )

        # TODO: check if it overwrites existing files

        temp_track_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_track_path, "wb") as out_handle:
            shutil.copyfileobj(encoded, out_handle)

        # build proper download path
        final_path = download_folder / relative_path

        if final_path.exists():
            log("track already exists? skipping")
        else:
            # move completed download
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(temp_track_path, final_path)

        return DownloadedTrack(final_path, relative_path, wave_id)
    except Exception as e:
        utils.log(e)
        return None
    finally:
        finish_progress(track)


class ProgressBar:
    task_id: TaskID

    def __init__(self, user: soundcloud.User, track: soundcloud.BasicTrack):
        self.task_id = rich_progress.add_task(
            "download",
            service="soundcloud",
            author=user.username,
            title=track.title,
            duration=track.duration,
            start=True,
            total=None,
        )

    def __del__(self):
        rich_progress.remove_task(self.task_id)


progresses: dict[int, ProgressBar] = dict()


def start_progress(user: soundcloud.User, track: soundcloud.BasicTrack):
    progresses[track.id] = ProgressBar(user, track)


def finish_progress(track: soundcloud.BasicTrack):
    if track.id in progresses:
        del progresses[track.id]
