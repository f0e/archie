from __future__ import annotations
from sqlalchemy import *
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker

import datetime

# TODO: handle this shit in main
db = create_engine('sqlite:///archive.db')
Session = sessionmaker(bind=db)
session = Session()

###
# Channel
###


class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = 'person'

    id = Column(String, primary_key=True)
    name = Column(Text)
    country = Column(String)
    channels = relationship('Channel', backref='person')


class Channel(Base):
    __tablename__ = 'channel'

    id = Column(String, primary_key=True)
    person_name = Column(Text, ForeignKey('person.name'), nullable=True)

    name = Column(Text)
    avatar = Column(BLOB)
    description = Column(Text)

    timestamp = Column(DateTime,
                       default=datetime.datetime.utcnow())

    # optional data
    notes = Column(Text, nullable=True)

    versions = relationship('ChannelVersion', backref='channel')
    comments = relationship('VideoComment', backref='channel')
    videos = relationship('Video', backref='channel')

    @classmethod
    def create_or_update(self, id, name, avatar, description) -> Channel:
        channel = session.query(Channel).filter(self.id == id).first()

        if not channel:
            session.add(Channel(
                id=id,
                name=name,
                avatar=avatar,
                description=description)
            )

            session.commit()

            return channel

        print('found existing channel!')

        # check if anything's changed
        if name == channel.name and\
                avatar == channel.avatar and\
                description == channel.description:
            return channel

        session.add(ChannelVersion(
            channel_id=channel.id,
            name=channel.name,
            avatar=channel.avatar,
            description=channel.description,
            timestamp=channel.timestamp)
        )

        # update new data
        channel.name = name
        channel.avatar = avatar
        channel.description = description
        channel.timestamp = datetime.datetime.utcnow()

        session.commit()

        return channel


class ChannelVersion(Base):
    __tablename__ = 'channel_version'

    channel_id = Column(Text, ForeignKey('channel.id'), primary_key=True)

    name = Column(Text)
    avatar = Column(BLOB)
    description = Column(Text)

    timestamp = Column(DateTime)

###
# Video
###


class Video(Base):
    __tablename__ = 'video'

    id = Column(String, primary_key=True)
    title = Column(Text)
    thumbnail = Column(BLOB)
    description = Column(Text, nullable=True)
    duration = Column(Float)
    author_id = Column(Text, ForeignKey('channel.id'))
    availability = Column(String)

    details = relationship('VideoDetails', backref='video', uselist=False)
    comments = relationship('VideoComment', backref='video')

    @classmethod
    def add(self, video) -> Video:
        session.add(video)
        session.commit()

        return video


class VideoDetails(Base):
    __tablename__ = 'video_details'

    video_id = Column(Text, ForeignKey('video.id'), primary_key=True)

###
# Comment
###


class VideoComment(Base):
    __tablename__ = 'video_comment'

    channel_id = Column(Text, ForeignKey('channel.id'), primary_key=True)
    video_id = Column(Text, ForeignKey('video.id'))


def connect():
    Base.metadata.create_all(db)


def close():
    db.dispose()
