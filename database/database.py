from __future__ import annotations
from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session

import datetime

#TODO: handle this shit in main
db = create_engine('archive.db', echo=True)
session = Session(engine)
Base = declarative_base()

###
# Channel
###

class Person(Base):
    __tablename__ = 'person'
    
    id = Column(String, primary_key=True)
    name = Column(Text)
    country = Column(String)
    channels = relationship('channel', backref='person')

class Channel(Base):
    __tablename__ = 'channel'
    
    id = Column(String, primary_key=True)
    person = Column(Text, ForeignKey('person.name'), nullable=False)

    name = Column(Text)
    avatar = Column(BLOB)
    description = Column(Text)

    timestamp = Column(DateTime,
        default=datetime.datetime.utcnow())

    # optional data
    notes = Column(Text, nullable=True)

    versions = relationship('channel_version', backref='channel')
    comments = relationship('video_comment', backref='channel')
    videos = relationship('video', backref='channel')

    @classmethod
    def create_or_update(self, id, name, avatar, description) -> Channel:
        channel = session.query(Channel).filter(self.id == id).first()
        
        if not channel:
            channel = Channel(
                id=id,
                name=name,
                avatar=avatar,
                description=description,
            )

            return channel

        # check if anything's changed
        if name == channel.name or\
                avatar == channel.avatar or\
                description == channel.description:
            return channel

        # store current state
        ChannelVersion(
            channel=channel,
            name=channel.name,
            avatar=channel.avatar,
            description=channel.description,
            timestamp=channel.timestamp
        )

        # update new data
        channel.name = name
        channel.avatar = avatar
        channel.description = description
        # todo:
        # channel.timestamp = SERVER TIME
        session.add(channel)
        
        return channel


class ChannelVersion(Base):
    __tablename__ = 'channel_version'
    
    channel_id = Column(Text, ForeignKey('channel.id'))

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
    description = Column(Text, nullable=True)
    duration = Column(Float)
    author_id = Column(Text, ForeignKey('channel.id'))
    
    details = relationship('video_details', backref='video')
    comments = relationship('video_comment', backref='video')


class VideoDetails(Base):
    __tablename__ = 'video_details'   
    
    video_id = Column(Text, ForeignKey('video.id'))

###
# Comment
###


class VideoComment(Base):
    __tablename__ = 'video_comment'
    
    channel_id = Column(Text, ForeignKey('channel.id'))
    video_id = Column(Text, ForeignKey('video.id'))


def connect():
    MetaData.create_all(db)

def close():
    db.dispose()
