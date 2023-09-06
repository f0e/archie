from __future__ import annotations

import enum
import typing
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import orm

from archie import ARCHIE_PATH
from archie.utils import utils


def log(*args, **kwargs):
    utils.safe_log("db", "white", *args, **kwargs)


# TODO: handle this shit in main
db_path = ARCHIE_PATH / "archie.db"
db = sa.create_engine(f"sqlite:///{db_path}")

session_factory = orm.sessionmaker(bind=db)
Session = orm.scoped_session(session_factory)

initialised = False

###
# Channel
###


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


class ChannelStatus(enum.Enum):
    QUEUED = 0
    ACCEPTED = 1
    REJECTED = 2


class Archive(Base):
    __tablename__ = "archive"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)
    name: orm.Mapped[str]

    channels: orm.Mapped[list[Channel]] = orm.relationship("Channel", secondary="archive_channels", back_populates="archives")

    @staticmethod
    def get(name: str):
        session = Session()

        archive = session.query(Archive).filter(Archive.name == name).first()

        # create the archive if it doesn't exist yet
        if not archive:
            archive = Archive(name=name)
            session.add(archive)
            session.commit()

        return archive

    def add_channel(self, channel: Channel, from_spider: bool):
        session = Session()

        if channel in self.channels:
            return channel

        session.add(ArchiveChannel(archive_id=self.id, channel_id=channel.id, from_spider=from_spider))
        session.commit()

        return channel

    def get_next_of_status(self, status: ChannelStatus, updated_before: datetime | None = None):
        session = Session()

        return (
            session.query(Channel)
            .filter(Channel.archives.any(id=self.id))
            .filter(Channel.status == status)
            .filter(
                sa.or_(
                    Channel.update_time.is_(None),
                    Channel.update_status != Channel.status,
                    Channel.update_time <= updated_before,
                )
            )
            .first()
        )


class ArchiveChannel(Base):
    __tablename__ = "archive_channels"

    archive_id = orm.mapped_column(sa.ForeignKey("archive.id"), primary_key=True)
    channel_id = orm.mapped_column(sa.ForeignKey("channel.id"), primary_key=True)

    from_spider: orm.Mapped[bool]


class Person(Base):
    __tablename__ = "person"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)
    name: orm.Mapped[str]
    country: orm.Mapped[str]

    # relationships
    channels: orm.Mapped[list[Channel]] = orm.relationship(back_populates="person", cascade="all, delete-orphan")


class Channel(Base):
    __tablename__ = "channel"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)

    status: orm.Mapped[ChannelStatus]

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
    update_time: orm.Mapped[datetime | None]
    update_status: orm.Mapped[ChannelStatus | None]

    # relationships
    versions: orm.Mapped[list[ChannelVersion]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")
    comments: orm.Mapped[list[VideoComment]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")
    videos: orm.Mapped[list[Video]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")

    # backref
    person_id: orm.Mapped[int | None] = orm.mapped_column(sa.ForeignKey("person.id"))
    person: orm.Mapped[Person | None] = orm.relationship(back_populates="channels")

    archives: orm.Mapped[list[Archive]] = orm.relationship("Archive", secondary="archive_channels", back_populates="channels")

    # indexes
    __table_args__ = (sa.Index("idx_status", "status"),)

    @staticmethod
    def get(id: str, fully_parsed: bool):
        session = Session()

        builder = session.query(Channel).filter(Channel.id == id)

        if fully_parsed:
            builder = builder.filter(Channel.update_time.is_not(None))

        return builder.first()

    @classmethod
    def create_or_update(
        self,
        status: ChannelStatus | None,
        id: str,
        name: str,
        avatar_url: str | None,
        banner_url: str | None,
        description: str,
        subscribers: int,
        tags_list: list[str],
        verified: bool,
    ) -> Channel:
        session = Session()

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
        title: str,
        thumbnail_url: str,
        description: str,
        duration: float,
        availability: str,
        views: int,
    ) -> Video:
        session = Session()

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
        session = Session()

        self.update_time = datetime.utcnow()
        self.update_status = self.status
        session.commit()

    def set_status(self, status: ChannelStatus):
        session = Session()

        self.status = status
        session.commit()


class ChannelVersion(Base):
    __tablename__ = "channel_version"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)

    channel_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("channel.id"))
    channel: orm.Mapped[Channel] = orm.relationship(back_populates="versions")

    name: orm.Mapped[str]
    avatar_url: orm.Mapped[str | None]
    banner_url: orm.Mapped[str | None]
    description: orm.Mapped[str]
    subscribers: orm.Mapped[int]

    update_time: orm.Mapped[datetime]


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
    comments: orm.Mapped[list[VideoComment]] = orm.relationship(back_populates="video", cascade="all, delete-orphan")
    downloads: orm.Mapped[list[VideoDownload]] = orm.relationship(back_populates="video", cascade="all, delete-orphan")

    # backref
    channel_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("channel.id"))
    channel: orm.Mapped[Channel] = orm.relationship(back_populates="videos")

    @staticmethod
    def get_next_download():
        session = Session()

        return (
            session.query(Video)
            .join(VideoDownload, isouter=True)
            .join(Channel)
            .where(VideoDownload.format.is_(None), Channel.status == ChannelStatus.ACCEPTED)
            .first()
        )

    def update_details(self, thumbnail_url: str, availability: str, categories_list: list[str], tags_list: list[str], timestamp: datetime):
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

    def add_download(self, path: Path, format: str):
        session = Session()

        download = VideoDownload(path=str(path), format=format)

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
    video: orm.Mapped[Video] = orm.relationship(back_populates="downloads")

    format: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    path: orm.Mapped[str]

    @staticmethod
    def get_downloads():
        session = Session()

        yield from session.query(VideoDownload)

    def delete(self):
        session = Session()

        session.delete(self)
        session.commit()


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
    replies: orm.Mapped[list[VideoComment]] = orm.relationship(back_populates="parent", remote_side=[id], uselist=True)
    # uselist=True cause for some reason it doesn't always use a list

    # backref
    channel_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("channel.id"))
    channel: orm.Mapped[Channel] = orm.relationship(back_populates="comments")

    video_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("video.id"))
    video: orm.Mapped[Video] = orm.relationship(back_populates="comments")

    parent_id: orm.Mapped[str | None] = orm.mapped_column(sa.ForeignKey("video_comment.id"))
    parent: orm.Mapped[VideoComment | None] = orm.relationship(back_populates="replies")


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
