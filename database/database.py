from __future__ import annotations
import sqlalchemy as sql
from sqlalchemy import orm
from utils.utils import download_image

import datetime

# TODO: handle this shit in main
db = sql.create_engine('sqlite:///archive.db')
Session = orm.sessionmaker(bind=db)
session = Session()

###
# Channel
###


class Base(orm.DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = 'person'

    id = sql.Column(sql.Integer, primary_key=True, autoincrement=True)
    name = sql.Column(sql.Text)
    country = sql.Column(sql.String)
    channels = orm.relationship('Channel', back_populates='person')


class Channel(Base):
    __tablename__ = 'channel'

    id = sql.Column(sql.String, primary_key=True)

    person_id = sql.Column(
        sql.Integer, sql.ForeignKey('person.id'), nullable=True)
    person = orm.relationship("Person", back_populates="channels")

    name = sql.Column(sql.Text)

    avatar_url = sql.Column(sql.String)
    banner_url = sql.Column(sql.String)

    description = sql.Column(sql.Text)
    subscribers = sql.Column(sql.Integer)
    tags = sql.Column(sql.Text)
    verified = sql.Column(sql.Boolean)

    timestamp = sql.Column(sql.DateTime,
                           default=datetime.datetime.utcnow())

    # optional data
    notes = sql.Column(sql.Text, nullable=True)

    versions = orm.relationship('ChannelVersion', back_populates='channel')
    comments = orm.relationship('VideoComment', back_populates='channel')
    videos = orm.relationship('Video', back_populates='channel')

    @classmethod
    def create_or_update(self, id: str, name: str, avatar_url: str, banner_url: str, description: str, subscribers: int, tags_list: list[str], verified: bool) -> Channel:
        channel = session.query(Channel).filter(self.id == id).first()

        tags = ",".join(tags_list)

        if not channel:
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

            session.add(channel)
            session.commit()

            return channel

        print('found existing channel!')

        # check if anything's changed
        if name == channel.name and \
                avatar_url == channel.avatar_url and \
                banner_url == channel.banner_url and \
                description == channel.description and \
                subscribers == channel.subscribers and \
                tags == channel.tags and \
                verified == channel.verified:
            return channel

        session.add(ChannelVersion(
            channel_id=channel.id,
            name=channel.name,
            avatar_url=channel.avatar_url,
            banner_url=channel.banner_url,
            description=channel.description,
            subscribers=channel.subscribers,
            tags=channel.tags,
            verified=channel.verified
        ))

        # update new data
        channel.name = name
        channel.avatar_url = avatar_url
        channel.banner_url = banner_url
        channel.description = description
        channel.subscribers = subscribers
        channel.tags = tags
        channel.verified = verified
        channel.timestamp = datetime.datetime.utcnow()

        session.commit()

        return channel

    def add_video(self, id: str, title: str, thumbnail_url: str, description: str, duration: float, availability: str, views: int) -> Video:
        existing_video = session.query(Video).filter_by(
            id=id, channel=self).first()

        video = Video(
            channel_id=self.id,

            id=id,
            title=title,
            thumbnail_url=thumbnail_url,
            description=description,
            duration=duration,
            availability=availability,
            views=views
        )

        if existing_video:
            existing_video = video
            # todo: store history
        else:
            session.add(video)

        session.commit()

        return video


class ChannelVersion(Base):
    __tablename__ = 'channel_version'

    id = sql.Column(sql.Integer, primary_key=True, autoincrement=True)

    channel_id = sql.Column(sql.String, sql.ForeignKey('channel.id'))
    channel = orm.relationship("Channel", back_populates="versions")

    name = sql.Column(sql.Text)
    avatar_url = sql.Column(sql.String)
    description = sql.Column(sql.Text)

    timestamp = sql.Column(sql.DateTime)

###
# Video
###


class Video(Base):
    __tablename__ = 'video'

    id = sql.Column(sql.String, primary_key=True)
    title = sql.Column(sql.Text)
    thumbnail_url = sql.Column(sql.String)
    description = sql.Column(sql.Text, nullable=True)
    duration = sql.Column(sql.Integer)
    views = sql.Column(sql.Integer)

    # only available on video page
    availability = sql.Column(sql.String, nullable=True)
    categories = sql.Column(sql.String, nullable=True)
    tags = sql.Column(sql.String, nullable=True)
    timestamp = sql.Column(sql.DateTime, nullable=True)

    channel_id = sql.Column(sql.String, sql.ForeignKey('channel.id'))
    channel = orm.relationship("Channel", back_populates="videos")

    comments = orm.relationship('VideoComment', back_populates='video')

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

    def add_comment(self, id: str, parent_id: str | None, text: str, likes: int, channel_id: str, channel_avatar_url: str, timestamp: datetime.datetime, favorited: bool):
        existing_comment = session.query(VideoComment).filter_by(
            id=id, video=self).first()

        comment = VideoComment(
            video_id=self.id,

            id=id,
            parent_id=parent_id,
            text=text,
            likes=likes,
            channel_id=channel_id,
            channel_avatar_url=channel_avatar_url,
            timestamp=timestamp,
            favorited=favorited
        )

        if existing_comment:
            existing_comment = comment
        else:
            session.add(comment)

        session.commit()

        return comment

###
# Comment
###


class VideoComment(Base):
    __tablename__ = 'video_comment'

    id = sql.Column(sql.String, primary_key=True)
    text = sql.Column(sql.Text)
    likes = sql.Column(sql.Integer)
    timestamp = sql.Column(sql.DateTime)
    favorited = sql.Column(sql.Boolean)

    channel_avatar_url = sql.Column(sql.String)

    parent_id = sql.Column(
        sql.String, sql.ForeignKey('video_comment.id'))
    parent = orm.relationship("VideoComment", back_populates="replies")
    replies = orm.relationship("VideoComment", remote_side=[
                               id], back_populates="parent")

    channel_id = sql.Column(sql.String, sql.ForeignKey('channel.id'))
    channel = orm.relationship("Channel", back_populates="comments")

    video_id = sql.Column(sql.String, sql.ForeignKey('video.id'))
    video = orm.relationship("Video", back_populates="comments")


def connect():
    Base.metadata.create_all(db)


def close():
    db.dispose()
