import json
import time
import yt_dlp

from utils.utils import download_image
from database.database import db, Channel
from . import filter


def debug_write(yt, data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(yt.sanitize_info(data)))


def get_page(yt, channel, page):
    return yt.extract_info(f'https://www.youtube.com/{channel}/{page}', download=False)


def add_channel(channel):
    # adds a channel to the database. will filter out unwanted channels.
    # only adds basic information on /about page

    ydl_opts = {
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        about = get_page(yt, channel, "about")
        if filter.filter_about(about):
            return False

        # todo: do all channels have at least one avatar? this will fail if not
        avatar_data = download_image(about['thumbnails'][0]['url'])

        Channel.create_or_update(
            id=about['id'],
            name=about['channel'],
            avatar=avatar_data,
            description=about['description']
        )

    return True


def update_channel(channel):
    # updates a channel's videos, playlists, etc.

    ydl_opts = {
        'extract_flat': True,
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        videos = get_page(yt, channel, "videos")
        if filter.filter_videos(videos):
            # todo: the channel's already been added but it's got too many videos or something
            # What To Do
            pass

    return True
