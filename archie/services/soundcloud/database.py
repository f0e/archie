from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import soundcloud

from ..base_mongo import db


def get_user(user_id):
    return db["soundcloud_users"].find_one({"user.id": user_id})


# TODO: these do not need to be vars anymore move them back into param types
UserScanSource = Literal["full", "repost", "like", "repost", "comment", "playlist", "track"]
UserStatus = Literal["accepted", "queued", "rejected"]


def update_indexes():
    db["soundcloud_users"].create_index("user.id", unique=True)
    db["soundcloud_tracks"].create_index("track.id", unique=True)
    db["soundcloud_playlists"].create_index("playlist.id", unique=True)
    db["soundcloud_comments"].create_index("comment.id", unique=True)
    db["soundcloud_track_downloads"].create_index("track_id")


def store_user(
    user: soundcloud.User,
    scan_source: UserScanSource,
    status: UserStatus,
    tracks: list[soundcloud.BasicTrack] = [],
    playlists: list[soundcloud.BasicAlbumPlaylist] = [],
    links: list[soundcloud.WebProfile] = [],
    reposts: list[soundcloud.RepostItem] = [],
):
    existing_db_user = get_user(user.id)
    # check to see if the user has already been added, and has been scanned fully.
    # if we're about to replace it with a partial scan then return.
    # TODO: could potentially update the user component only, since it might have changed, but i'd rather keep it simple for now
    if existing_db_user and existing_db_user["_scan_source"] == "full" and scan_source != "full":
        return

    db_user = {
        "_scan_time": datetime.now(timezone.utc),
        "_scan_source": scan_source,
        "_status": status if not existing_db_user else existing_db_user["_status"],
        "user": asdict(user),
        "tracks": [],
        "playlists": [],
        "links": [asdict(link) for link in links],
        "track_reposts": [],
        "playlist_reposts": [],
    }

    for track in tracks:
        db_user["tracks"].append(track.id)
        store_track(track, "user")

    for playlist in playlists:
        db_user["playlists"].append(playlist.id)
        store_playlist(playlist)

    for _repost in reposts:
        repost = asdict(_repost)
        del repost["user"]  # type: ignore

        repost["user_id"] = _repost.user.id

        # store user if new
        if _repost.user.id != user.id and not get_user(_repost.user.id):
            store_user(_repost.user, "repost", "queued")

        if type(_repost) is soundcloud.TrackStreamRepostItem:
            del repost["track"]  # type: ignore
            repost["track_id"] = _repost.track.id

            db_user["track_reposts"].append(repost)

            store_track(_repost.track, "repost")
        elif type(_repost) is soundcloud.PlaylistStreamRepostItem:
            del repost["playlist"]  # type: ignore
            repost["playlist_id"] = _repost.playlist.id

            db_user["playlist_reposts"].append(repost)

            store_playlist(_repost.playlist)

    if not db["soundcloud_users"].find_one_and_replace({"user.id": user.id}, db_user):
        db["soundcloud_users"].insert_one(db_user)


def get_track(track_id: int):
    return db["soundcloud_tracks"].find_one({"track.id": track_id})


TrackScanSource = Literal["full", "user", "repost", "playlist"]


def store_track(
    track: soundcloud.BasicTrack | soundcloud.MiniTrack,
    scan_source: TrackScanSource,
    albums: list[soundcloud.BasicAlbumPlaylist] = [],
    comments: list[soundcloud.BasicComment] = [],
    likers: list[soundcloud.User] = [],
    reposters: list[soundcloud.User] = [],
    playlists: list[soundcloud.BasicAlbumPlaylist] = [],
):
    is_mini = type(track) is soundcloud.MiniTrack

    existing_db_track = get_track(track.id)
    # check to see if the track has already been added, and has been scanned fully.
    # if we're about to replace it with a partial scan then return.
    # TODO: could potentially update the track component only, since it might have changed, but i'd rather keep it simple for now
    if existing_db_track and existing_db_track["_scan_source"] == "full" and scan_source != "full":
        return

    db_track: dict = {
        "_scan_time": datetime.now(timezone.utc),
        "_scan_source": scan_source,
        "track": asdict(track),
    }

    if is_mini:
        db_track["is_mini"] = True
    else:
        del db_track["track"]["user"]  # type: ignore
        store_user(track.user, "track", "queued")

    db_track["albums"] = []
    for album in albums:
        db_track["albums"].append(album.id)
        store_playlist(album)

    db_track["comments"] = []
    for comment in comments:
        db_track["comments"].append(comment.id)
        store_comment(comment)

    db_track["likers"] = []
    for liker in likers:
        db_track["likers"].append(liker.id)

        if liker.id != track.user_id and not get_user(liker.id):
            store_user(liker, "like", "queued")

    db_track["reposters"] = []
    for reposter in reposters:
        db_track["reposters"].append(reposter.id)

        if reposter.id != track.user_id and not get_user(reposter.id):
            store_user(reposter, "repost", "queued")

    db_track["playlists"] = []
    for playlist in playlists:
        db_track["playlists"].append(playlist.id)
        store_playlist(playlist)

    if not db["soundcloud_tracks"].find_one_and_replace({"track.id": track.id}, db_track):
        db["soundcloud_tracks"].insert_one(db_track)

    # store(
    #     key,
    #     DbTrack(
    #         TrackMeta(),
    #         track,
    #         albums,
    #         comments,
    #         likers,
    #         reposters,
    #         playlists,
    #     ),
    # )


def store_comment(comment: soundcloud.BasicComment):
    db_comment = {
        "_scan_time": datetime.now(timezone.utc),
        "comment": asdict(comment),
        "user_id": comment.user_id,
    }

    del db_comment["comment"]["user"]

    store_user(comment.user, "comment", "queued")

    if not db["soundcloud_comments"].find_one_and_replace({"comment.id": comment.id}, db_comment):
        db["soundcloud_comments"].insert_one(db_comment)


def store_playlist(playlist: soundcloud.BasicAlbumPlaylist):
    existing_db_playlist = db["soundcloud_playlists"].find_one({"playlist.id": playlist.id})
    if existing_db_playlist:
        return

    db_playlist = {"_scan_time": datetime.now(timezone.utc), "playlist": asdict(playlist), "track_ids": []}

    del db_playlist["playlist"]["user"]  # type: ignore
    store_user(playlist.user, "playlist", "queued")

    del db_playlist["playlist"]["tracks"]  # type: ignore
    db_playlist["track_ids"] = []
    for track in playlist.tracks:
        db_playlist["track_ids"].append(track.id)  # type: ignore
        store_track(track, "playlist")

    if not db["soundcloud_playlists"].find_one_and_replace({"playlist.id": playlist.id}, db_playlist):
        db["soundcloud_playlists"].insert_one(db_playlist)


def get_track_to_parse(min_update_time: datetime):
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
                "from": "soundcloud_users",
                "localField": "track.user_id",
                "foreignField": "user.id",
                "as": "user_info",
            }
        },
        {
            "$match": {
                "user_info._status": "accepted",
            }
        },
    ]

    return db["soundcloud_tracks"].aggregate(pipeline)


def get_undownloaded_track(skip_ids: list[int]):
    pipeline = [
        {
            "$match": {
                "_scan_source": "full",
                "track.id": {
                    "$nin": skip_ids,
                },
            }
        },
        {
            "$lookup": {
                "from": "soundcloud_track_downloads",
                "localField": "track.id",
                "foreignField": "track_id",
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

    res = db["soundcloud_tracks"].aggregate(pipeline)

    return next(res, None)


def store_download(track_id: int, path: Path, relative_video_path: Path, wave: str):
    db["soundcloud_track_downloads"].insert_one(
        {
            "_download_time": datetime.now(timezone.utc),
            "track_id": track_id,
            "path": str(path),
            "relative_video_path": str(relative_video_path),
            "wave": wave,
        }
    )


def get_downloads():
    for download in db["soundcloud_track_downloads"].find():
        yield download


def remove_download(mongo_id: str):
    db["soundcloud_track_downloads"].delete_one({"_id": mongo_id})
