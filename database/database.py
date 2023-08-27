import peewee
import datetime

db = peewee.SqliteDatabase('archive.db')


class BaseModel(peewee.Model):
    class Meta:
        database = db

###
# Channel
###


class Person(BaseModel):
    id = peewee.CharField(primary_key=True)
    name = peewee.TextField()
    country = peewee.CharField()


class Channel(BaseModel):
    id = peewee.CharField(primary_key=True)
    person = peewee.ForeignKeyField(Person, backref='person', null=True)

    name = peewee.TextField()
    avatar = peewee.BlobField()
    description = peewee.TextField()

    timestamp = peewee.DateTimeField(
        constraints=[peewee.SQL('DEFAULT CURRENT_TIMESTAMP')])

    # optional data
    notes = peewee.TextField(null=True)

    @classmethod
    def create_or_update(self, id, name, avatar, description):
        channel = self.select().where(self.id == id).first()

        if not channel:
            channel = self.create(
                id=id,
                name=name,
                avatar=avatar,
                description=description,
            )

            return

        # check if anything's changed
        if name == channel.name or\
                avatar == channel.avatar or\
                description == channel.description:
            return

        # store current state
        ChannelVersion.create(
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
        channel.save()


class ChannelVersion(BaseModel):
    channel = peewee.ForeignKeyField(Channel, backref='versions')

    name = peewee.TextField()
    avatar = peewee.BlobField()
    description = peewee.TextField()

    timestamp = peewee.DateTimeField()

###
# Video
###


class Video(BaseModel):
    id = peewee.CharField(primary_key=True)
    title = peewee.TextField()
    description = peewee.TextField(null=True)
    duration = peewee.FloatField()
    author = peewee.ForeignKeyField(Channel, backref='videos')


class VideoDetails(BaseModel):
    video = peewee.ForeignKeyField(Video, backref='details', unique=True)

###
# Comment
###


class VideoComment(BaseModel):
    author = peewee.ForeignKeyField(Channel, backref='comments')
    video = peewee.ForeignKeyField(Video, backref='comments')


def connect():
    db.connect()
    db.create_tables([Person,
                      Channel,
                      ChannelVersion,
                      Video,
                      VideoDetails,
                      VideoComment])


def close():
    db.close()
