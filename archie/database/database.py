from __future__ import annotations
import typing
import sqlalchemy as sa
from sqlalchemy import orm
from datetime import datetime
import enum
from contextlib import contextmanager

from ..utils import utils

from .. import ARCHIE_PATH


def log(*args, **kwargs):
    print("[db] " + " ".join(map(str, args)), **kwargs)


# TODO: handle this shit in main
db_path = ARCHIE_PATH / "archie.db"
db = sa.create_engine(f"sqlite:///{db_path}")
Session = orm.sessionmaker(bind=db)
session = Session()

###
# Channel
###


class Base(orm.DeclarativeBase):
    def __repr__(self) -> str:
        return self._repr(id=self.id)

    def _repr(self, **fields: typing.Dict[str, typing.Any]) -> str:
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


class ChannelStatus(enum.Enum):
    QUEUED = 0
    ACCEPTED = 1
    REJECTED = 2


class Person(Base):
    __tablename__ = "person"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)
    name: orm.Mapped[str]
    country: orm.Mapped[str]

    # relationships
    channels: orm.Mapped[typing.List["Channel"]] = orm.relationship(back_populates="person", cascade="all, delete-orphan")


class Channel(Base):
    __tablename__ = "channel"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)

    status: orm.Mapped[ChannelStatus]

    # tracked
    name: orm.Mapped[str]
    avatar_url: orm.Mapped[str]
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
    update_time: orm.Mapped[datetime | None]
    update_status: orm.Mapped[ChannelStatus | None]

    # relationships
    versions: orm.Mapped[typing.List["ChannelVersion"]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")
    comments: orm.Mapped[typing.List["VideoComment"]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")
    videos: orm.Mapped[typing.List["Video"]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")

    # backref
    person_id: orm.Mapped[int | None] = orm.mapped_column(sa.ForeignKey("person.id"))
    person: orm.Mapped[typing.Optional["Person"]] = orm.relationship(back_populates="channels")

    # indexes
    __table_args__ = (sa.Index("idx_status", "status"),)

    @staticmethod
    def get_next_of_status(status: ChannelStatus, updated_before: datetime = None):
        return (
            session.query(Channel)
            .filter(
                Channel.status == status, sa.or_(Channel.update_time == None, Channel.update_status != Channel.status, Channel.update_time <= updated_before)
            )
            .first()
        )

    @staticmethod
    def get(id: str):
        return session.query(Channel).filter_by(id=id).first()

    @classmethod
    def create_or_update(
        self,
        status: ChannelStatus | None,
        id: str,
        name: str,
        avatar_url: str,
        banner_url: str | None,
        description: str,
        subscribers: int,
        tags_list: list[str],
        verified: bool,
    ) -> Channel:
        tags = ",".join(tags_list)

        existing_channel = session.query(Channel).filter_by(id=id).first()
        new_channel = existing_channel or Channel()

        if existing_channel:
            changes = False

            for var in self._tracked:
                if getattr(new_channel, var) != getattr(existing_channel, var):
                    changes = True
                    break

            if changes:
                log(f"storing history for channel {name} ({id})")

                session.add(
                    ChannelVersion(
                        channel_id=existing_channel.id,
                        name=existing_channel.name,
                        avatar_url=existing_channel.avatar_url,
                        banner_url=existing_channel.banner_url,
                        description=existing_channel.description,
                        subscribers=existing_channel.subscribers,
                        timestamp=existing_channel.timestamp,
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

    def add_or_update_video(self, id: str, title: str, thumbnail_url: str, description: str, duration: float, availability: str, views: int) -> Video:
        existing_video = utils.find(self.videos, lambda x: x.id == id)
        new_video = existing_video or Video()

        # set fields
        new_video.id = id
        new_video.title = title
        new_video.thumbnail_url = thumbnail_url
        new_video.description = description
        new_video.duration = duration
        new_video.availability = availability
        new_video.views = views

        if not existing_video:
            self.videos.append(new_video)

        session.commit()

        return new_video

    def set_updated(self):
        self.update_time = datetime.utcnow()
        self.update_status = self.status
        session.commit()

    def set_status(self, status: ChannelStatus):
        self.status = status
        session.commit()


class ChannelVersion(Base):
    __tablename__ = "channel_version"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)

    channel_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("channel.id"))
    channel: orm.Mapped["Channel"] = orm.relationship(back_populates="versions")

    name: orm.Mapped[str]
    avatar_url: orm.Mapped[str]
    banner_url: orm.Mapped[str]
    description: orm.Mapped[str]
    subscribers: orm.Mapped[int]

    timestamp: orm.Mapped[datetime]


###
# Video
###


class Video(Base):
    __tablename__ = "video"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    title: orm.Mapped[str]
    thumbnail_url: orm.Mapped[str]
    description: orm.Mapped[str | None]
    duration: orm.Mapped[int]
    views: orm.Mapped[int]

    fully_parsed: orm.Mapped[bool] = orm.mapped_column(default=False)

    # only available on video page
    availability: orm.Mapped[str | None]
    categories: orm.Mapped[str | None]
    tags: orm.Mapped[str | None]
    timestamp: orm.Mapped[datetime | None]

    # archie data
    update_time: orm.Mapped[datetime | None]

    # relationships
    comments: orm.Mapped[typing.List["VideoComment"]] = orm.relationship(back_populates="video", cascade="all, delete-orphan")
    downloads: orm.Mapped[typing.List["VideoDownload"]] = orm.relationship(back_populates="video", cascade="all, delete-orphan")

    # backref
    channel_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("channel.id"))
    channel: orm.Mapped["Channel"] = orm.relationship(back_populates="videos")

    @staticmethod
    def get_next_download():
        return (
            session.query(Video)
            .join(VideoDownload, isouter=True)
            .join(Channel)
            .where(VideoDownload.format == None, Channel.status == ChannelStatus.ACCEPTED)
            .first()
        )

    @classmethod
    def add(video) -> Video:
        session.add(video)
        session.commit()

        return video

    def update_details(self, thumbnail_url: str, availability: str, categories_list: list[str], tags_list: list[str], timestamp: datetime):
        self.thumbnail_url = thumbnail_url
        self.availability = availability
        self.categories = ",".join(categories_list)
        self.tags = ",".join(tags_list)
        self.timestamp = timestamp

        session.commit()

    def add_comment(
        self, id: str, parent_id: str | None, channel_id: str, text: str, likes: int, channel_avatar_url: str, timestamp: datetime, favorited: bool
    ):
        existing_comment = utils.find(self.comments, lambda x: x.id == id)
        new_comment = existing_comment or VideoComment()

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

    def add_download(self, path: str, format: str):
        download = VideoDownload(path=path, format=format)

        self.downloads.append(download)
        session.commit()

        return download

    def set_updated(self):
        self.update_time = datetime.utcnow()

        if not self.fully_parsed:
            self.fully_parsed = True


class VideoDownload(Base):
    __tablename__ = "video_download"

    # backref
    video_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("video.id"), primary_key=True)
    video: orm.Mapped["Video"] = orm.relationship(back_populates="downloads")

    format: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    path: orm.Mapped[str]


###
# Comment
###


class VideoComment(Base):
    __tablename__ = "video_comment"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    text: orm.Mapped[str]
    likes: orm.Mapped[int]
    timestamp: orm.Mapped[datetime]
    favorited: orm.Mapped[bool]

    channel_avatar_url: orm.Mapped[str]

    # relationships
    replies: orm.Mapped[typing.List["VideoComment"]] = orm.relationship(back_populates="parent", remote_side=[id], uselist=True)
    # uselist=True cause for some reason it doesn't always use a list

    # backref
    channel_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("channel.id"))
    channel: orm.Mapped["Channel"] = orm.relationship(back_populates="comments")

    video_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("video.id"))
    video: orm.Mapped["Video"] = orm.relationship(back_populates="comments")

    parent_id: orm.Mapped[str | None] = orm.mapped_column(sa.ForeignKey("video_comment.id"))
    parent: orm.Mapped[typing.Optional["VideoComment"]] = orm.relationship(back_populates="replies")


def connect():
    Base.metadata.create_all(db)


def close():
    db.dispose()


@contextmanager
def database_connection():
    try:
        connect()
        yield
    finally:
        close()
