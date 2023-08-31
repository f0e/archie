from database.database import Channel, ChannelStatus
from sources import youtube


def log(message):
    print("[parse] " + message)


def parse_accepted_channels():
    # goes through accepted channels videos
    while True:
        channel = Channel.get_next_of_status(ChannelStatus.ACCEPTED)
        if not channel:
            break

        videos = youtube.parse_videos(channel)

        for video in videos:
            youtube.parse_video_details(video)

        log(f"finished parsing {channel.name} ({channel.id})")

    log("finished parsing accepted channels")


def init():
    START_CHANNEL = '@em-pq6uv'
    if Channel.get(START_CHANNEL):
        return

    youtube.parse_channel(START_CHANNEL, ChannelStatus.ACCEPTED)
