import json
import datetime
from typing import Dict
import yt_dlp

from database.database import Channel, Video, VideoComment
from . import filter


def log(message):
    print("[youtube] " + message)


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
        avatar_url = None
        banner_url = None
        for image in about['thumbnails']:
            if image['id'] == 'avatar_uncropped':
                avatar_url = image['url']
            elif image['id'] == 'banner_uncropped':
                banner_url = image['url']

        channel = Channel.create_or_update(
            id=about['channel_id'],
            name=about['channel'],
            avatar_url=avatar_url,
            banner_url=banner_url,
            description=about['description'],
            subscribers=about['channel_follower_count'],
            tags_list=about['tags'],
            verified=about.get('channel_is_verified')
        )

        log(f"added channel {channel.name} ({channel.id})")

        parse_videos(channel)

    return True


def parse_videos(channel):
    # updates a channel's videos, playlists, etc.

    ydl_opts = {
        # don't get videos, just get the data available from the /videos page
        'extract_flat': True,
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        videos = yt.extract_info(
            f'https://www.youtube.com/channel/{channel.id}/videos', download=False)

        debug_write(yt, videos, "videos-author")

        if filter.filter_videos(videos):
            # todo: what to do when the channel's already been added
            pass

        # channel.update_videos(videos)

        # for video in videos parse_video_details

        for entry in videos['entries']:
            video = channel.add_video(
                id=entry['id'],
                title=entry['title'],
                # placeholder, get better quality thumbnail in parse_video_details
                thumbnail_url=entry['thumbnails'][0]['url'],
                description=entry['description'],
                duration=entry['duration'],
                availability=entry['availability'],
                views=entry['view_count']
            )

            log(f"added video {video.title} for channel {channel.id} ({video.id})")

            parse_video_details(video)

    return True


def parse_video_details(video):
    # gets all info and commenters for a video

    ydl_opts = {
        'getcomments': True,
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        data = yt.extract_info(
            f'https://www.youtube.com/watch?v={video.id}', download=False)

        if filter.filter_video(data):
            # todo: what to do when the video's already been added
            pass

        video.update_details(
            thumbnail_url=data['thumbnail'],
            categories_list=data['categories'],
            tags_list=data['tags'],
            availability=data['availability'],
            timestamp=datetime.datetime.utcfromtimestamp(data['epoch']),
        )

        if data['comments']:
            for comment in data['comments']:
                comment = video.add_comment(
                    id=comment['id'],
                    parent_id=comment['parent'],
                    text=comment['text'],
                    likes=comment['like_count'],
                    channel_id=comment['author_id'],
                    channel_avatar_url=comment['author_thumbnail'],
                    timestamp=datetime.datetime.utcfromtimestamp(
                        comment['timestamp']),
                    favorited=comment['is_favorited']
                )

        log(f"parsed video details, got {len(video.comments)} comments")

    return True
