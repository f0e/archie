import json
import yt_dlp

from utils.utils import download_image
from database.database import Channel
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

        # get avatar and banner
        avatar_data = None
        banner_data = None
        for image in about['thumbnails']:
            if image['id'] == 'avatar_uncropped':
                avatar_data = download_image(image['url'])
            elif image['id'] == 'banner_uncropped':
                banner_data = download_image(image['url'])

        channel = Channel.create_or_update(
            id=about['channel_id'],
            name=about['channel'],
            avatar=avatar_data,
            banner=banner_data,
            description=about['description'],
            subscribers=about['channel_follower_count'],
            tags_list=about['tags'],
            verified=about.get('channel_is_verified')
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
