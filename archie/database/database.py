from __future__ import annotations

import enum
import threading
import typing
from contextlib import contextmanager
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import orm

from archie import ARCHIE_PATH
from archie.utils import utils


def log(*args, **kwargs):
    utils.module_log("db", "white", *args, **kwargs)


# TODO: handle this shit in main
db_path = ARCHIE_PATH / "archie.db"
db = sa.create_engine(f"sqlite:///{db_path}")

session_factory = orm.sessionmaker(bind=db)
Session = orm.scoped_session(session_factory)

initialised = False

download_lock = threading.Lock()


class Base(orm.DeclarativeBase):
    def __repr__(self) -> str:
        if isinstance(self, orm.DeclarativeBase):
            return self._repr(**{c.key: getattr(self, c.key) for c in self.__table__.columns})
        return super().__repr__()

    def _repr(self, **fields: dict[str, typing.Any]) -> str:
        """
        Helper for __repr__
        """
        field_strings = []
        at_least_one_attached_attribute = False
        for key, field in fields.items():
            try:
                field_strings.append(f"{key}={field!r}")
            except sa.orm.exc.DetachedInstanceError:
                field_strings.append(f"{key}=DetachedInstanceError")
            else:
                at_least_one_attached_attribute = True
        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"
        return f"<{self.__class__.__name__} {id(self)}>"


class AccountStatus(enum.Enum):
    QUEUED = 0
    ACCEPTED = 1
    REJECTED = 2


###
# YouTube
###


class YouTubeAccount(Base):
    __tablename__ = "youtube_account"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)

    status: orm.Mapped[AccountStatus]

    # tracked
    name: orm.Mapped[str]
    avatar_url: orm.Mapped[str | None]
    banner_url: orm.Mapped[str | None]
    description: orm.Mapped[str]
    subscribers: orm.Mapped[int]
    _tracked = ["name", "avatar_url", "banner_url", "description", "subscribers"]

    # misc
    tags: orm.Mapped[str]
    verified: orm.Mapped[bool]

    # optional user defined data
    notes: orm.Mapped[str | None]

    # archie data
    fully_parsed: orm.Mapped[bool] = orm.mapped_column(default=False)
    update_time: orm.Mapped[datetime | None]
    update_status: orm.Mapped[AccountStatus | None]

    # relationships
    versions: orm.Mapped[list[YouTubeAccountVersion]] = orm.relationship(
        back_populates="youtube_account", cascade="all, delete-orphan"
    )
    comments: orm.Mapped[list[YouTubeVideoComment]] = orm.relationship(
        back_populates="youtube_account", cascade="all, delete-orphan"
    )
    youtube_videos: orm.Mapped[list[YouTubeVideo]] = orm.relationship(
        back_populates="youtube_account", cascade="all, delete-orphan"
    )
    playlists: orm.Mapped[list[YouTubePlaylist]] = orm.relationship(
        back_populates="youtube_account", cascade="all, delete-orphan"
    )

    # indexes
    __table_args__ = (sa.Index("idx_status", "status"),)

    @staticmethod
    def get(id: str, fully_parsed: bool):
        session = Session()

        builder = session.query(YouTubeAccount).filter(YouTubeAccount.id == id)

        if fully_parsed:
            builder = builder.filter(YouTubeAccount.update_time.is_not(None))

        return builder.first()

    @classmethod
    def create_or_update(
        cls,
        status: AccountStatus | None,
        id: str,
        name: str,
        avatar_url: str | None,
        banner_url: str | None,
        description: str,
        subscribers: int,
        tags: list[str],
        verified: bool,
    ) -> YouTubeAccount:
        session = Session()

        existing_channel = session.query(YouTubeAccount).filter_by(id=id).first()
        new_channel = existing_channel or YouTubeAccount()

        if existing_channel:
            changes = False

            for var in cls._tracked:
                if getattr(new_channel, var) != getattr(existing_channel, var):
                    changes = True
                    break

            if changes:
                log(f"storing history for channel {name} ({id})")

                session.add(
                    YouTubeAccountVersion(
                        channel_id=existing_channel.id,
                        name=existing_channel.name,
                        avatar_url=existing_channel.avatar_url,
                        banner_url=existing_channel.banner_url,
                        description=existing_channel.description,
                        subscribers=existing_channel.subscribers,
                        update_time=existing_channel.update_time,
                    )
                )

        # set fields
        if status:
            new_channel.status = status

        new_channel.id = id
        new_channel.name = name
        new_channel.avatar_url = avatar_url
        new_channel.banner_url = banner_url
        new_channel.description = description
        new_channel.subscribers = subscribers
        new_channel.tags = tags
        new_channel.verified = verified

        if not existing_channel:
            session.add(new_channel)

        session.commit()

        return new_channel

    def add_or_update_video(
        self,
        id: str,
        title: str | None,
        thumbnail_url: str | None,
        description: str | None,
        duration: float | None,
        availability: str | None,
        views: int | None,
        playlist: YouTubePlaylist | None = None,
    ) -> YouTubeVideo:
        return YouTubeVideo.create_or_update(
            self.id,
            id,
            title,
            thumbnail_url,
            description,
            duration,
            availability,
            views,
            playlist,
        )

    def add_or_update_playlist(
        self,
        id: str,
        title: str,
        availability: str,
        description: str,
        tags_list: list[str],
        thumbnail_url: str,
        modified_date: str,
        view_count: int,
        channel_id: str,
        videos,
    ):
        tags = ",".join(tags_list)

        session = Session()

        existing_playlist = utils.find(self.playlists, lambda x: x.id == id)
        new_playlist = existing_playlist or YouTubePlaylist()

        # TODO: handle playlist changes

        new_playlist.id = id
        new_playlist.title = title
        new_playlist.availability = availability
        new_playlist.description = description
        new_playlist.tags = tags
        new_playlist.thumbnail_url = thumbnail_url
        new_playlist.modified_date = datetime.fromisoformat(modified_date)
        new_playlist.view_count = view_count
        new_playlist.channel_id = channel_id
        new_playlist.timestamp = datetime.utcnow()

        for video in videos:
            if video["channel_id"] is None:  # deleted video etc
                YouTubeVideo.create_or_update(
                    id=video["id"],
                    channel_id=None,
                    title=None,
                    thumbnail_url=None,
                    description=None,
                    duration=None,
                    availability="unavailable",
                    views=None,
                    playlist=new_playlist,
                )
            else:
                YouTubeVideo.create_or_update(
                    id=video["id"],
                    channel_id=video["channel_id"],
                    title=video["title"],
                    thumbnail_url=video["thumbnails"][0]["url"],
                    description=video["description"],
                    duration=video["duration"],
                    availability=video["availability"],
                    views=video["view_count"],
                    playlist=new_playlist,
                )

        if not existing_playlist:
            session.add(new_playlist)

        session.commit()

        return new_playlist

    def set_updated(self):
        session = Session()

        self.update_time = datetime.utcnow()
        self.update_status = self.status

        if not self.fully_parsed:
            self.fully_parsed = True

        session.commit()

    def set_status(self, status: AccountStatus):
        session = Session()

        self.status = status
        session.commit()


class YouTubeAccountVersion(Base):
    __tablename__ = "youtube_account_version"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)

    youtube_account_id_fk: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("youtube_account.id"))
    youtube_account: orm.Mapped[YouTubeAccount] = orm.relationship(back_populates="versions")

    name: orm.Mapped[str]
    avatar_url: orm.Mapped[str | None]
    banner_url: orm.Mapped[str | None]
    description: orm.Mapped[str]
    subscribers: orm.Mapped[int]

    update_time: orm.Mapped[datetime]


class YouTubeVideo(Base):
    __tablename__ = "youtube_video"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    title: orm.Mapped[str | None]
    thumbnail_url: orm.Mapped[str | None]
    description: orm.Mapped[str | None]
    duration: orm.Mapped[int | None]
    views: orm.Mapped[int | None]

    fully_parsed: orm.Mapped[bool] = orm.mapped_column(default=False)

    # only available on video page
    availability: orm.Mapped[str | None]
    categories: orm.Mapped[str | None]
    tags: orm.Mapped[str | None]
    timestamp: orm.Mapped[datetime | None]

    # archie data
    downloading: orm.Mapped[bool] = orm.mapped_column(default=False)
    update_time: orm.Mapped[datetime | None]

    # relationships
    comments: orm.Mapped[list[YouTubeVideoComment]] = orm.relationship(
        back_populates="youtube_video", cascade="all, delete-orphan"
    )
    # downloads: orm.Mapped[list[ContentDownload]] = orm.relationship(back_populates="youtube_video", cascade="all, delete-orphan")
    playlists_in: orm.Mapped[list[YouTubePlaylist]] = orm.relationship(
        "YouTubePlaylist", secondary="youtube_playlist_video", back_populates="youtube_videos"
    )

    # backref
    youtube_account_id_fk: orm.Mapped[str | None] = orm.mapped_column(sa.ForeignKey("youtube_account.id"))
    youtube_account: orm.Mapped[YouTubeAccount | None] = orm.relationship(back_populates="youtube_videos")

    @staticmethod
    def get(id: str):
        session = Session()
        return session.query(YouTubeVideo).filter(YouTubeVideo.id == id).first()

    # @staticmethod
    # def get_next_download():
    #     with download_lock:  # need to wait for other threads to set downloading=True
    #         session = Session()

    #         video = (
    #             session.query(YouTubeVideo)
    #             .where(YouTubeVideo.downloading == sa.false())
    #             .join(ContentDownload, isouter=True)
    #             .join(YouTubeAccount)
    #             .where(ContentDownload.format.is_(None), YouTubeAccount.status == AccountStatus.ACCEPTED)
    #             .first()
    #         )

    #         if video:
    #             video.downloading = True
    #             session.commit()

    #         return video

    @staticmethod
    def reset_download_states():
        session = Session()
        session.query(YouTubeVideo).update({YouTubeVideo.downloading: False})
        session.commit()

    @classmethod
    def create_or_update(
        cls,
        channel_id: str | None,
        id: str,
        title: str | None,
        thumbnail_url: str | None,
        description: str | None,
        duration: float | None,
        availability: str | None,
        views: int | None,
        playlist: YouTubePlaylist | None = None,
    ) -> YouTubeVideo:
        session = Session()

        existing_video = session.query(YouTubeVideo).filter_by(id=id).first()

        new_video = existing_video or YouTubeVideo()

        # set fields
        new_video.id = id
        new_video.channel_id = channel_id
        new_video.title = title
        new_video.thumbnail_url = thumbnail_url
        new_video.description = description
        new_video.duration = duration
        new_video.availability = availability
        new_video.views = views

        if playlist:
            existing_playlist = utils.find(new_video.playlists_in, lambda x: x.id == playlist.id)

            if not existing_playlist:
                new_video.playlists_in.append(playlist)

        if not existing_video:
            session.add(new_video)

        session.commit()

        return new_video

    def update_details(
        self, thumbnail_url: str, availability: str, categories_list: list[str], tags_list: list[str], timestamp: datetime
    ):
        session = Session()

        self.thumbnail_url = thumbnail_url
        self.availability = availability
        self.categories = ",".join(categories_list)
        self.tags = ",".join(tags_list)
        self.timestamp = timestamp

        session.commit()

    def add_comment(
        self,
        id: str,
        parent_id: str | None,
        channel_id: str,
        text: str,
        likes: int,
        channel_avatar_url: str,
        timestamp: datetime,
        favorited: bool,
    ):
        session = Session()

        existing_comment = utils.find(self.comments, lambda x: x.id == id)
        new_comment = existing_comment or YouTubeVideoComment()

        # set fields
        new_comment.video_id = self.id
        new_comment.id = id
        new_comment.parent_id = parent_id
        new_comment.channel_id = channel_id
        new_comment.text = text
        new_comment.likes = likes
        new_comment.channel_avatar_url = channel_avatar_url
        new_comment.timestamp = timestamp
        new_comment.favorited = favorited

        if not existing_comment:
            self.comments.append(new_comment)

        session.commit()

        return new_comment

    # def add_download(self, path: Path, format: str):
    #     session = Session()

    #     self.downloading = False

    #     download = ContentDownload(path=str(path), format=format)
    #     self.downloads.append(download)

    #     session.commit()

    #     return download

    def set_updated(self):
        session = Session()

        self.update_time = datetime.utcnow()

        if not self.fully_parsed:
            self.fully_parsed = True

        session.commit()


class ContentDownload(Base):
    __tablename__ = "content_download"

    format: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    path: orm.Mapped[str]

    @staticmethod
    def get_downloads():
        session = Session()
        yield from session.query(ContentDownload)

    def delete(self):
        session = Session()

        session.delete(self)
        session.commit()


###
# YouTube Comment
###


class YouTubeVideoComment(Base):
    __tablename__ = "youtube_video_comment"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    text: orm.Mapped[str]
    likes: orm.Mapped[int]
    timestamp: orm.Mapped[datetime]
    favorited: orm.Mapped[bool]

    channel_avatar_url: orm.Mapped[str]

    # relationships
    replies: orm.Mapped[list[YouTubeVideoComment]] = orm.relationship(back_populates="parent", remote_side=[id], uselist=True)
    # uselist=True cause for some reason it doesn't always use a list

    # backref
    youtube_account_id_fk: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("youtube_account.id"))
    youtube_account: orm.Mapped[YouTubeAccount] = orm.relationship(back_populates="comments")
    youtube_video_id_fk: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("youtube_video.id"))
    youtube_video: orm.Mapped[YouTubeVideo] = orm.relationship(back_populates="comments")
    parent_id_fk: orm.Mapped[str | None] = orm.mapped_column(sa.ForeignKey("youtube_video_comment.id"))
    parent: orm.Mapped[YouTubeVideoComment | None] = orm.relationship(back_populates="replies")


class YouTubePlaylistVideo(Base):
    __tablename__ = "youtube_playlist_video"

    playlist_id = orm.mapped_column(sa.ForeignKey("youtube_playlist.id"), primary_key=True)
    video_id = orm.mapped_column(sa.ForeignKey("youtube_video.id"), primary_key=True)


class YouTubePlaylist(Base):
    __tablename__ = "youtube_playlist"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    title: orm.Mapped[str]
    view_count: orm.Mapped[int | None]
    thumbnail_url: orm.Mapped[str | None]
    availability: orm.Mapped[str]
    description: orm.Mapped[str | None]
    tags: orm.Mapped[str | None]

    # relationships
    youtube_videos: orm.Mapped[list[YouTubeVideo]] = orm.relationship(
        "YouTubeVideo", secondary="youtube_playlist_video", back_populates="playlists_in"
    )

    # backrefs
    youtube_account_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("youtube_account.id"))
    youtube_account: orm.Mapped[YouTubeAccount] = orm.relationship(back_populates="playlists")

    # versions: orm.Mapped[list[PlaylistVersion]] = orm.relationship(back_populates="playlist", cascade="all, delete-orphan") #TODO: playlist versions

    modified_date: orm.Mapped[datetime | None]

    # TODO: for playlist versioning
    timestamp: orm.Mapped[datetime | None]

    def add_video(self, video: YouTubeVideo):
        session = Session()

        if video in self.videos:
            return video

        session.add(YouTubePlaylistVideo(playlist_id=self.id, video_id=video.id))
        session.commit()

        return video


def initialise():
    global initialised
    if initialised:
        return

    Base.metadata.create_all(db)
    initialised = True


def detach():
    global initialised
    db.dispose()
    initialised = False


@contextmanager
def connect():
    try:
        initialise()
        yield
    finally:
        detach()
