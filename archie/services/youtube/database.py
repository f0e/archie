from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yt_dlp

from ..base_mongo import db


def update_indexes():
    db["youtube_channels"].create_index("channel.id", unique=True)
    db["youtube_videos"].create_index("video.id", unique=True)
    db["youtube_playlists"].create_index("playlist.id", unique=True)
    db["youtube_video_downloads"].create_index("video_id")


def get_channel(channel_id: str):
    return db["youtube_channels"].find_one({"channel.id": channel_id})


def store_channel(
    channel: dict,
    videos: list[dict],
    playlists: list[dict],
    scan_source: Literal["full", "comment"],
    status: Literal["accepted", "queued", "rejected"],
):
    existing_db_channel = get_channel(channel["id"])
    # check to see if the user has already been added, and has been scanned fully.
    # if we're about to replace it with a partial scan then return.
    # TODO: could potentially update the user component only, since it might have changed, but i'd rather keep it simple for now
    if existing_db_channel and existing_db_channel["_scan_source"] == "full" and scan_source != "full":
        return

    db_channel = {
        "_scan_source": scan_source,
        "_status": status if not existing_db_channel else existing_db_channel["_status"],
        "_scan_time": datetime.now(timezone.utc),
        "channel": channel,
    }

    db_channel["video_ids"] = []
    for video in videos:
        db_channel["video_ids"].append(video["id"])
        store_video(video, "channel")

    db_channel["playlist_ids"] = []
    for playlist in playlists:
        db_channel["playlist_ids"].append(playlist["id"])
        store_playlist(playlist, [], "channel", "queued")

    if not db["youtube_channels"].find_one_and_replace({"channel.id": channel["id"]}, db_channel):
        db["youtube_channels"].insert_one(db_channel)


def get_playlist(playlist_id: str):
    return db["youtube_playlists"].find_one({"playlist.id": playlist_id})


def store_playlist(
    playlist: dict, videos: list[dict], scan_source: Literal["full", "channel"], status: Literal["accepted", "queued", "rejected"]
):
    existing_db_playlist = get_playlist(playlist["id"])
    # check to see if the user has already been added, and has been scanned fully.
    # if we're about to replace it with a partial scan then return.
    # TODO: could potentially update the user component only, since it might have changed, but i'd rather keep it simple for now
    if existing_db_playlist and existing_db_playlist["_scan_source"] == "full" and scan_source != "full":
        return

    db_playlist = {
        "_scan_source": scan_source,
        "_status": status if not existing_db_playlist else existing_db_playlist["_status"],
        "_scan_time": datetime.now(timezone.utc),
        "playlist": playlist,
    }

    db_playlist["video_ids"] = []
    for video in videos:
        db_playlist["video_ids"].append(video["id"])
        store_video(video, "playlist")

    if not db["youtube_playlists"].find_one_and_replace({"playlist.id": playlist["id"]}, db_playlist):
        db["youtube_playlists"].insert_one(db_playlist)


def get_video(video_id: str):
    return db["youtube_videos"].find_one({"video.id": video_id})


def store_video_error(video_id: str, error: yt_dlp.utils.YoutubeDLError):
    scan_time = datetime.now(timezone.utc)

    # parsing video failed. if we got to this point then it *was* fully parsed, it just didn't return anything useful
    # don't bother replacing the data with nothing, just update the scan time.
    # TODO: if versioning is added maybe replacing the data with nothing is better, but for now i want to retain it

    db_video_fail = {
        "_scan_time": scan_time,
        "_scan_source": "full",
        "error": error.msg,
    }

    if not db["youtube_videos"].find_one_and_update(
        {"video.id": video_id},
        {"$set": db_video_fail},
    ):
        db["youtube_videos"].insert_one(
            {
                **db_video_fail,
                "video": {"id": video_id},
            }
        )


def store_video(video: dict, scan_source: Literal["full", "channel", "playlist"]):
    existing_db_video = get_video(video["id"])
    # check to see if the user has already been added, and has been scanned fully.
    # if we're about to replace it with a partial scan then return.
    # TODO: could potentially update the user component only, since it might have changed, but i'd rather keep it simple for now
    if existing_db_video and existing_db_video["_scan_source"] == "full" and scan_source != "full":
        return

    db_video = {
        "_scan_source": scan_source,
        "_scan_time": datetime.now(timezone.utc),
        "video": video,
    }

    # TODO: store comments in separate collection like soundcloud?
    # if "comments" in video and video["comments"]:
    #     # del db_video["video"]["comments"]
    #     for comment in video["comments"]:
    #         store_channel(
    #             {
    #                 "id": comment["author_id"],
    #                 "author": comment["author"],
    #                 "author_thumbnail": comment["author_thumbnail"],
    #                 "timestamp": comment["timestamp"],
    #             },
    #             [],
    #             [],
    #             "comment",
    #             "queued",
    #         )

    if not db["youtube_videos"].find_one_and_replace({"video.id": video["id"]}, db_video):
        db["youtube_videos"].insert_one(db_video)


def get_playlist_to_parse(min_update_time: datetime):
    pipeline = [
        {
            "$match": {
                "$or": [
                    {
                        "_scan_source": {
                            "$ne": "full",
                        },
                    },
                    {
                        "_scan_time": {
                            "$lt": min_update_time,
                        }
                    },
                ]
            }
        },
        {
            "$lookup": {
                "from": "youtube_channels",
                "localField": "playlist.channel_id",
                "foreignField": "channel.id",
                "as": "channel_info",
            }
        },
        {
            "$match": {
                "channel_info._status": "accepted",
            }
        },
    ]

    return db["youtube_playlists"].aggregate(pipeline)


def get_video_to_parse(min_update_time: datetime):
    pipeline = [
        {
            "$match": {
                "error": {
                    "$exists": False,
                }
            }
        },
        {
            "$match": {
                "$or": [
                    {
                        "_scan_source": {
                            "$ne": "full",
                        },
                    },
                    {
                        "_scan_time": {
                            "$lt": min_update_time,
                        }
                    },
                ]
            }
        },
        {
            "$lookup": {
                "from": "youtube_channels",
                "localField": "video.channel_id",
                "foreignField": "channel.id",
                "as": "channel_info",
            }
        },
        {
            "$match": {
                "channel_info._status": "accepted",
            }
        },
    ]

    return db["youtube_videos"].aggregate(pipeline)


def get_undownloaded_video(skip_ids: list[str]):
    pipeline = [
        {
            "$match": {
                "_scan_source": "full",
                "video.id": {
                    "$nin": skip_ids,
                },
                "video.duration": {
                    "$lt": 130,
                },
            }
        },
        {
            "$lookup": {
                "from": "youtube_channels",
                "localField": "video.channel_id",
                "foreignField": "channel.id",
                "as": "channel_info",
            }
        },
        {
            "$match": {
                "channel_info._status": "accepted",
            }
        },
        {
            "$lookup": {
                "from": "youtube_video_downloads",
                "localField": "video.id",
                "foreignField": "video_id",
                "as": "download_info",
            }
        },
        {
            "$match": {
                "download_info": {
                    "$eq": [],
                }
            }
        },
        {
            "$project": {
                "download_info": 0,
            }
        },
        {
            "$limit": 1,
        },
    ]

    res = db["youtube_videos"].aggregate(pipeline)

    return next(res, None)


def store_download(video_id: str, path: Path, relative_video_path: Path, format: str):
    db_download = {
        "_download_time": datetime.now(timezone.utc),
        "video_id": video_id,
        "path": str(path),
        "relative_video_path": str(relative_video_path),
        "format": format,
    }

    db["youtube_video_downloads"].insert_one(db_download)


def get_downloads():
    for download in db["youtube_video_downloads"].find():
        yield download


def remove_download(mongo_id: str):
    db["youtube_video_downloads"].delete_one({"_id": mongo_id})
