from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal, Tuple

import dacite
import dateutil.parser as dp
import orjson
import redis
import soundcloud

from archie.services.base_redis import get_undownloaded_id

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


class DbObject:
    dacite_config = dacite.Config(type_hooks={datetime: dp.isoparse}, cast=[tuple])

    @classmethod
    def from_dict(cls, d: dict):
        return dacite.from_dict(cls, d, cls.dacite_config)


def store(key, data: DbObject):
    return r.set(key, orjson.dumps(data, default=str))


def get(key):
    data = r.get(key)
    if not data:
        return data

    return orjson.loads(data)


ScanSourceType = Literal["full", "comment"]
StatusType = Literal["accepted", "queued", "rejected"]


@dataclass
class UserMeta:
    scan_source: ScanSourceType
    status: StatusType
    scan_time = datetime.now(timezone.utc)


@dataclass
class DbUser(DbObject):
    meta: UserMeta
    user: soundcloud.User
    tracks: list[soundcloud.BasicTrack]
    playlists: list[soundcloud.BasicAlbumPlaylist]
    links: list[soundcloud.WebProfile]
    track_reposts: list[soundcloud.TrackStreamRepostItem]
    playlist_reposts: list[soundcloud.PlaylistStreamRepostItem]


def get_user(user_id) -> DbUser | None:
    key = f"soundcloud:user:{user_id}"

    data = get(key)
    if not data:
        return None

    data["user"] = soundcloud.User.from_dict(data["user"])
    data["tracks"] = [soundcloud.BasicTrack.from_dict(o) for o in data["tracks"]]
    data["playlists"] = [soundcloud.BasicAlbumPlaylist.from_dict(o) for o in data["playlists"]]
    data["links"] = [soundcloud.WebProfile.from_dict(o) for o in data["links"]]
    data["track_reposts"] = [soundcloud.TrackStreamRepostItem.from_dict(o) for o in data["track_reposts"]]
    data["playlist_reposts"] = [soundcloud.PlaylistStreamRepostItem.from_dict(o) for o in data["playlist_reposts"]]

    return DbUser.from_dict(data)


def store_user(
    user: soundcloud.User,
    tracks: list[soundcloud.BasicTrack],
    playlists: list[soundcloud.BasicAlbumPlaylist],
    links: list[soundcloud.WebProfile],
    reposts: list[soundcloud.RepostItem],
    scan_source: ScanSourceType,
    status: StatusType,
):
    key = f"soundcloud:user:{user.id}"

    # bit silly but separate them out before to make life easier
    track_reposts = []
    playlist_reposts = []
    for repost in reposts:
        if type(repost) == soundcloud.TrackStreamRepostItem:
            track_reposts.append(repost)
        elif type(repost) == soundcloud.PlaylistStreamRepostItem:
            playlist_reposts.append(repost)

    store(
        key,
        DbUser(
            UserMeta(scan_source, status),
            user,
            tracks,
            playlists,
            links,
            track_reposts,
            playlist_reposts,
        ),
    )


@dataclass
class TrackMeta:
    scan_time = datetime.now(timezone.utc)


@dataclass
class DbTrack(DbObject):
    meta: TrackMeta
    track: soundcloud.BasicTrack
    albums: list[soundcloud.BasicAlbumPlaylist]
    comments: list[soundcloud.BasicComment]
    likers: list[soundcloud.User]
    reposters: list[soundcloud.User]
    playlists: list[soundcloud.BasicAlbumPlaylist]


def get_track(track_id: int) -> DbTrack | None:
    key = f"soundcloud:track:{track_id}"

    data = get(key)
    if not data:
        return None

    data["albums"] = [soundcloud.BasicAlbumPlaylist.from_dict(o) for o in data["albums"]]
    data["comments"] = [soundcloud.BasicComment.from_dict(o) for o in data["comments"]]
    data["likers"] = [soundcloud.User.from_dict(o) for o in data["likers"]]
    data["reposters"] = [soundcloud.User.from_dict(o) for o in data["reposters"]]
    data["playlists"] = [soundcloud.BasicAlbumPlaylist.from_dict(o) for o in data["playlists"]]

    return DbTrack.from_dict(data)


def store_track(
    track_id: int,
    track: soundcloud.BasicTrack,  # TODO: this is duplicated from user
    albums: list[soundcloud.BasicAlbumPlaylist],
    comments: list[soundcloud.BasicComment],
    likers: list[soundcloud.User],
    reposters: list[soundcloud.User],
    playlists: list[soundcloud.BasicAlbumPlaylist],
):
    key = f"soundcloud:track:{track_id}"

    store(
        key,
        DbTrack(
            TrackMeta(),
            track,
            albums,
            comments,
            likers,
            reposters,
            playlists,
        ),
    )


def get_undownloaded_track(skip_ids: list[str]):
    undownloaded_id = get_undownloaded_id(r, "soundcloud", "track", skip_ids)
    if not undownloaded_id:
        return None

    return get_track(undownloaded_id)


@dataclass
class DownloadMeta:
    download_time = datetime.now(timezone.utc)


@dataclass
class DbDownload(DbObject):
    meta: DownloadMeta
    path: Path
    relative_video_path: Path
    wave: str


def get_download(track_id: int) -> DbDownload | None:
    key = f"soundcloud:download:{track_id}"

    data = get(key)
    if not data:
        return None

    data["path"] = Path(data["path"])
    data["relative_video_path"] = Path(data["relative_video_path"])

    return DbDownload.from_dict(data)


def store_download(track_id: int, path: Path, relative_video_path: Path, wave: str):
    key = f"soundcloud:download:{track_id}"

    store(key, DbDownload(DownloadMeta(), path, relative_video_path, wave))


def get_downloads() -> Iterator[Tuple[int, DbDownload | None]]:
    all_downloads = r.keys("soundcloud:download:*")

    # TODO: pipeline maybe if this is super slow

    for download_key in all_downloads:
        track_id = int(download_key.split(":")[-1])

        yield track_id, get_download(track_id)


def remove_download(track_id: int):
    key = f"soundcloud:download:{track_id}"

    r.delete(key)
