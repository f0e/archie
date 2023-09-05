from datetime import datetime, timedelta

from .database.database import Channel, ChannelStatus
from .sources import youtube
from .utils.config import settings


def log(*args, **kwargs):
    print("[parse] " + " ".join(map(str, args)), **kwargs)


def parse_accepted_channels():
    # goes through accepted channels videos
    while True:
        channel = Channel.get_next_of_status(ChannelStatus.ACCEPTED, datetime.utcnow() - timedelta(hours=settings.channel_update_gap_hours))
        if not channel:
            break

        log(f"updating channel {channel.name} ({channel.id})")
        youtube.update_channel(channel)

        video_min_update_time = datetime.utcnow() - timedelta(hours=settings.video_update_gap_hours)

        for video in channel.videos:
            if video.fully_parsed:
                if video.update_time > video_min_update_time:
                    continue

            youtube.parse_video_details(video)

        log(f"finished parsing {channel.name} ({channel.id})")

    log("finished parsing accepted channels")


def init():
    START_CHANNEL = 'UC3V9Tsy08G41oXr6TIg9xIw'
    if Channel.get(START_CHANNEL):
        return

    youtube.parse_channel('channel/' + START_CHANNEL, ChannelStatus.ACCEPTED)
