from __future__ import annotations
import sqlalchemy as sql
from sqlalchemy import orm

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
    avatar = sql.Column(sql.BLOB)
    banner = sql.Column(sql.BLOB)
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
    def create_or_update(self, id: str, name: str, avatar: bytes | None, banner: bytes | None, description: str, subscribers: int, tags_list: list[str], verified: bool) -> Channel:
        channel = session.query(Channel).filter(self.id == id).first()

        tags = ",".join(tags_list)

        if not channel:
            session.add(Channel(
                id=id,
                name=name,
                avatar=avatar,
                banner=banner,
                description=description,
                subscribers=subscribers,
                tags=tags,
                verified=verified
            ))

            session.commit()

            return channel

        print('found existing channel!')

        # check if anything's changed
        if name == channel.name and \
                avatar == channel.avatar and \
                banner == channel.banner and \
                description == channel.description and \
                subscribers == channel.subscribers and \
                tags == channel.tags and \
                verified == channel.verified:
            return channel

        session.add(ChannelVersion(
            channel_id=channel.id,
            name=channel.name,
            avatar=channel.avatar,
            banner=channel.banner,
            description=channel.description,
            subscribers=channel.subscribers,
            tags=channel.tags,
            verified=channel.verified
        ))

        # update new data
        channel.name = name
        channel.avatar = avatar
        channel.banner = banner
        channel.description = description
        channel.subscribers = subscribers
        channel.tags = tags
        channel.verified = verified
        channel.timestamp = datetime.datetime.utcnow()

        session.commit()

        return channel


class ChannelVersion(Base):
    __tablename__ = 'channel_version'

    id = sql.Column(sql.Integer, primary_key=True, autoincrement=True)

    channel_id = sql.Column(sql.String, sql.ForeignKey('channel.id'))
    channel = orm.relationship("Channel", back_populates="versions")

    name = sql.Column(sql.Text)
    avatar = sql.Column(sql.BLOB)
    description = sql.Column(sql.Text)

    timestamp = sql.Column(sql.DateTime)

###
# Video
###


class Video(Base):
    __tablename__ = 'video'

    id = sql.Column(sql.String, primary_key=True)
    title = sql.Column(sql.Text)
    description = sql.Column(sql.Text, nullable=True)
    duration = sql.Column(sql.Float)

    channel_id = sql.Column(sql.String, sql.ForeignKey('channel.id'))
    channel = orm.relationship("Channel", back_populates="videos")

    details = orm.relationship(
        'VideoDetails', back_populates='video', uselist=False)
    comments = orm.relationship('VideoComment', back_populates='video')


class VideoDetails(Base):
    __tablename__ = 'video_details'

    id = sql.Column(sql.Integer, primary_key=True, autoincrement=True)

    video_id = sql.Column(sql.String, sql.ForeignKey('video.id'))
    video = orm.relationship("Video", back_populates="details")

###
# Comment
###


class VideoComment(Base):
    __tablename__ = 'video_comment'

    id = sql.Column(sql.Integer, primary_key=True, autoincrement=True)

    channel_id = sql.Column(sql.String, sql.ForeignKey('channel.id'))
    channel = orm.relationship("Channel", back_populates="comments")

    video_id = sql.Column(sql.String, sql.ForeignKey('video.id'))
    video = orm.relationship("Video", back_populates="comments")


def connect():
    Base.metadata.create_all(db)


def close():
    db.dispose()
