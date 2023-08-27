import json
import time
import yt_dlp

from utils.utils import download_image
from database.database import db, Channel
from . import filter


def debug_write(yt, data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(yt.sanitize_info(data)))


def parse_channel(channelLink):
    # adds a channel to the database. will filter out unwanted channels.
    # only adds basic information on /about page

    ydl_opts = {
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        about = yt.extract_info(
            f'https://www.youtube.com/{channelLink}/about', download=False)

        if filter.filter_about(about):
            # todo: what to do when the channel's already been added
            return False

        # todo: do all channels have at least one avatar? this will fail if not
        avatar_data = download_image(about['thumbnails'][0]['url'])

        channel = Channel.create_or_update(
            id=about['channel_id'],
            name=about['channel'],
            avatar=avatar_data,
            description=about['description']
        )

        parse_video_details(channel)

    return True


def parse_video_details(channel):
    # updates a channel's videos, playlists, etc.

    ydl_opts = {
        # don't get videos, just get the data available from the /videos page
        'extract_flat': True,
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        videos = yt.extract_info(
            f'https://www.youtube.com/channel/{channel.id}/videos', download=False)

        if filter.filter_videos(videos):
            # todo: what to do when the channel's already been added
            pass

        # channel.update_videos(videos)

        # for video in videos parse_video_details

    return True


def parse_video_details(video):
    pass
