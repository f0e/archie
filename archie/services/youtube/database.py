import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def store(key, data_json):
    return r.set(key, json.dumps(data_json, default=str))


def get(key):
    data = r.get(key)
    if not data:
        return data

    return json.loads(data)


def get_channel(channel_id: str):
    key = f"youtube:channel:{channel_id}"

    return get(key)


def store_channel(
    channel: dict,
    videos: list[dict],
    playlists: list[dict],
    scan_source: Literal["full", "comment"],
    status: Literal["accepted", "queued", "rejected"],
):
    key = f"youtube:channel:{channel['id']}"

    store(
        key,
        {
            "meta": {
                "scan_source": scan_source,
                "status": status,
                "scan_time": datetime.now(timezone.utc),
                # todo: add archie version to everything?
            },
            "channel": channel,
            "videos": videos,
            "playlists": playlists,
        },
    )


def get_playlist(playlist_id: str):
    key = f"youtube:playlist:{playlist_id}"

    return get(key)


def store_playlist(
    playlist: dict, videos: list[dict], scan_source: Literal["full"], status: Literal["accepted", "queued", "rejected"]
):
    key = f"youtube:playlist:{playlist['id']}"

    store(
        key,
        {
            "meta": {"scan_source": scan_source, "status": status, "scan_time": datetime.now(timezone.utc)},
            "playlist": playlist,
            "videos": videos,
        },
    )


def get_video(video_id: str):
    key = f"youtube:video:{video_id}"

    return get(key)


def store_video(video: dict):
    key = f"youtube:video:{video['id']}"

    store(
        key,
        {
            "meta": {"scan_time": datetime.now(timezone.utc)},
            "video": video,
        },
    )


def get_undownloaded_video(skip_ids: list[str]):
    all_videos = r.keys("youtube:video:*")

    for video_key in all_videos:
        video_id = video_key.split(":")[-1]

        if video_id in skip_ids:
            continue

        download_key = f"youtube:download:{video_id}"
        if not r.get(download_key):
            return get(video_key)

    return None


def store_download(video_id: str, path: Path, relative_video_path: Path, format: str):
    key = f"youtube:download:{video_id}"

    store(
        key,
        {
            "meta": {"download_time": datetime.now(timezone.utc)},
            "path": path,
            "relative_video_path": relative_video_path,
            "format": format,
        },
    )


def get_downloads():
    all_downloads = r.keys("youtube:download:*")

    for download_key in all_downloads:
        video_id = download_key.split(":")[-1]

        yield video_id, get(download_key)


def remove_download(video_id: str):
    key = f"youtube:download:{video_id}"

    r.delete(key)
