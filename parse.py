from datetime import datetime, timedelta

from database.database import Channel, ChannelStatus
from sources import youtube

CHANNEL_UPDATE_GAP_HOURS = 24
VIDEO_UPDATE_GAP_HOURS = 24 * 7  # will only run when a channel is updated too


def log(message):
    print("[parse] " + message)


def parse_accepted_channels():
    # goes through accepted channels videos
    while True:
        channel = Channel.get_next_of_status(ChannelStatus.ACCEPTED, datetime.utcnow() - timedelta(hours=CHANNEL_UPDATE_GAP_HOURS))
        if not channel:
            break

        log(f"updating channel {channel.name} ({channel.id})")
        youtube.update_channel(channel)

        video_min_update_time = datetime.utcnow() - timedelta(hours=VIDEO_UPDATE_GAP_HOURS)

        for video in channel.videos:
            if video.update_time > video_min_update_time:
                continue

            log(f"updating video {video.title} by {channel.name} ({video.id})")
            youtube.parse_video_details(video)

        log(f"finished parsing {channel.name} ({channel.id})")

    log("finished parsing accepted channels")


def init():
    START_CHANNEL = 'UC3V9Tsy08G41oXr6TIg9xIw'
    if Channel.get(START_CHANNEL):
        return

    youtube.parse_channel('channel/' + START_CHANNEL, ChannelStatus.ACCEPTED)
