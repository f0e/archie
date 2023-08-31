from __future__ import annotations
import typing
import sqlalchemy as sa
from sqlalchemy import orm
from utils import utils

import datetime
import enum


def log(message):
    print("[db] " + message)


# TODO: handle this shit in main
db = sa.create_engine('sqlite:///archive.db')
Session = orm.sessionmaker(bind=db)
session = Session()

###
# Channel
###


class Base(orm.DeclarativeBase):
    def __repr__(self) -> str:
        return self._repr(id=self.id)

    def _repr(self, **fields: typing.Dict[str, typing.Any]) -> str:
        '''
        Helper for __repr__
        '''
        field_strings = []
        at_least_one_attached_attribute = False
        for key, field in fields.items():
            try:
                field_strings.append(f'{key}={field!r}')
            except sa.orm.exc.DetachedInstanceError:
                field_strings.append(f'{key}=DetachedInstanceError')
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
    __tablename__ = 'person'

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)
    name: orm.Mapped[str]
    country: orm.Mapped[str]

    # relationships
    channels: orm.Mapped[typing.List["Channel"]] = orm.relationship(back_populates="person", cascade="all, delete-orphan")


class Channel(Base):
    __tablename__ = 'channel'

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)

    status: orm.Mapped[ChannelStatus] = orm.mapped_column(sa.Enum(ChannelStatus))

    # tracked
    name: orm.Mapped[str]
    avatar_url: orm.Mapped[str]
    banner_url: orm.Mapped[str | None]
    description: orm.Mapped[str]
    subscribers: orm.Mapped[int]
    _tracked = ['name', 'avatar_url', 'banner_url', 'description', 'subscribers']

    # misc
    tags: orm.Mapped[str]
    verified: orm.Mapped[bool]

    timestamp: orm.Mapped[datetime.datetime] = orm.mapped_column(default=datetime.datetime.utcnow())

    # optional user defined data
    notes: orm.Mapped[str | None]

    # relationships
    versions: orm.Mapped[typing.List["ChannelVersion"]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")
    comments: orm.Mapped[typing.List["VideoComment"]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")
    videos: orm.Mapped[typing.List["Video"]] = orm.relationship(back_populates="channel", cascade="all, delete-orphan")

    # backref
    person_id: orm.Mapped[int | None] = orm.mapped_column(sa.ForeignKey("person.id"))
    person: orm.Mapped[typing.Optional["Person"]] = orm.relationship(back_populates="channels")

    # indexes
    __table_args__ = (
        sa.Index('idx_status', 'status'),
    )

    @staticmethod
    def get_next_of_status(status: ChannelStatus):
        return session.query(Channel).filter_by(status=status).first()

    @staticmethod
    def get(id: str):
        return session.query(Channel).filter_by(id=id).first()

    @classmethod
    def create_or_update(self, status: ChannelStatus | None, id: str, name: str, avatar_url: str, banner_url: str | None, description: str, subscribers: int, tags_list: list[str], verified: bool) -> Channel:
        existing_channel = session.query(Channel).filter_by(id=id).first()

        tags = ",".join(tags_list)

        channel = Channel(
            id=id,
            name=name,
            avatar_url=avatar_url,
            banner_url=banner_url,
            description=description,
            subscribers=subscribers,
            tags=tags,
            verified=verified
        )

        if status:
            channel.status = status

        if existing_channel:
            changes = False

            for var in self._tracked:
                if getattr(channel, var) != getattr(existing_channel, var):
                    changes = True
                    break

            if changes:
                log(f"storing history for channel {name} ({id})")

                session.add(ChannelVersion(
                    channel_id=channel.id,
                    name=channel.name,
                    avatar_url=channel.avatar_url,
                    banner_url=channel.banner_url,
                    description=channel.description,
                    subscribers=channel.subscribers
                ))

            existing_channel = channel
        else:
            session.add(channel)

        session.commit()

        return channel

    def set_status(self, status: ChannelStatus):
        self.status = status
        session.commit()

    def add_or_update_video(self, id: str, title: str, thumbnail_url: str, description: str, duration: float, availability: str, views: int) -> Video:
        existing_video = utils.find(self.videos, lambda x: x.id == id)

        video = Video(
            id=id,
            title=title,
            thumbnail_url=thumbnail_url,
            description=description,
            duration=duration,
            availability=availability,
            views=views
        )

        if existing_video:
            # todo: store history
            log("updating existing video")
            existing_video = video
        else:
            self.videos.append(video)

        session.commit()

        return video


class ChannelVersion(Base):
    __tablename__ = 'channel_version'

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)

    channel_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("channel.id"))
    channel: orm.Mapped["Channel"] = orm.relationship(back_populates="versions")

    name: orm.Mapped[str]
    avatar_url: orm.Mapped[str]
    banner_url: orm.Mapped[str]
    description: orm.Mapped[str]
    subscribers: orm.Mapped[int]
    name: orm.Mapped[str]

    timestamp: orm.Mapped[datetime.datetime]

###
# Video
###


class Video(Base):
    __tablename__ = 'video'

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    title: orm.Mapped[str]
    thumbnail_url: orm.Mapped[str]
    description: orm.Mapped[str | None]
    duration: orm.Mapped[int]
    views: orm.Mapped[int]

    # only available on video page
    availability: orm.Mapped[str | None]
    categories: orm.Mapped[str | None]
    tags: orm.Mapped[str | None]
    timestamp: orm.Mapped[datetime.datetime | None]

    # relationships
    comments: orm.Mapped[typing.List["VideoComment"]] = orm.relationship(back_populates="video", cascade="all, delete-orphan")

    # backref
    channel_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("channel.id"))
    channel: orm.Mapped["Channel"] = orm.relationship(back_populates="videos")

    @classmethod
    def add(video) -> Video:
        session.add(video)
        session.commit()

        return video

    def update_details(self, thumbnail_url: str, availability: str, categories_list: list[str], tags_list: list[str], timestamp: datetime.datetime):
        self.thumbnail_url = thumbnail_url
        self.availability = availability
        self.categories = ",".join(categories_list)
        self.tags = ",".join(tags_list)
        self.timestamp = timestamp

        session.commit()

    def add_comment(self, id: str, parent_id: str | None, channel_id: str, text: str, likes: int, channel_avatar_url: str, timestamp: datetime.datetime, favorited: bool):
        existing_comment = utils.find(self.comments, lambda x: x.id == id)

        comment = VideoComment(
            video_id=self.id,

            id=id,
            parent_id=parent_id,
            channel_id=channel_id,
            text=text,
            likes=likes,
            channel_avatar_url=channel_avatar_url,
            timestamp=timestamp,
            favorited=favorited
        )

        if existing_comment:
            # todo: store history
            log("updating existing comment")
            existing_comment = comment
        else:
            self.comments.append(comment)

        session.commit()

        return comment

###
# Comment
###


class VideoComment(Base):
    __tablename__ = 'video_comment'

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    text: orm.Mapped[str]
    likes: orm.Mapped[int]
    timestamp: orm.Mapped[datetime.datetime]
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
