import json
import datetime
from typing import Dict
import yt_dlp

from database.database import Channel, ChannelStatus, Video, VideoComment
from . import filter


def log(message):
    print("[youtube] " + message)


def debug_write(yt, data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(yt.sanitize_info(data)))


def parse_channel(channelLink: str, status: ChannelStatus) -> Channel | None:
    # adds a channel to the database. will filter out unwanted channels.
    # only adds basic information on /about page

    ydl_opts = {
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        about = yt.extract_info(f'https://www.youtube.com/{channelLink}/about', download=False)

        if filter.filter_about(about):
            # todo: what to do when the channel's already been added
            return None

        # get avatar and banner
        avatar_url = None
        banner_url = None
        for image in about['thumbnails']:
            if image['id'] == 'avatar_uncropped':
                avatar_url = image['url']
            elif image['id'] == 'banner_uncropped':
                banner_url = image['url']

        verified = False
        if 'channel_is_verified' in about:
            verified = about['channel_is_verified']

        subscribers = about['channel_follower_count'] or 0

        channel = Channel.create_or_update(
            status=status,
            id=about['channel_id'],
            name=about['channel'],
            avatar_url=avatar_url,
            banner_url=banner_url,
            description=about['description'],
            subscribers=subscribers,
            tags_list=about['tags'],
            verified=verified
        )

        log(f"parsed channel {channel.name} ({channel.id})")

        return channel


def parse_videos(channel: Channel):
    # updates a channel's videos, playlists, etc.

    ydl_opts = {
        # don't get videos, just get the data available from the /videos page
        'extract_flat': True,
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        data = yt.extract_info(f'https://www.youtube.com/channel/{channel.id}/videos', download=False)

        if filter.filter_videos(data):
            # todo: what to do when the channel's already been added
            pass

        videos = []

        for entry in data['entries']:
            video = channel.add_or_update_video(
                id=entry['id'],
                title=entry['title'],
                thumbnail_url=entry['thumbnails'][0]['url'],  # placeholder, get better quality thumbnail in parse_video_details
                description=entry['description'],
                duration=entry['duration'],
                availability=entry['availability'],
                views=entry['view_count']
            )

            log(f"parsed video {video.title} for channel {channel.id} ({video.id})")
            videos.append(video)

        return videos


def parse_video_details(video: Video):
    # gets all info and commenters for a video

    ydl_opts = {
        'getcomments': True,
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        data = yt.extract_info(f'https://www.youtube.com/watch?v={video.id}', download=False)

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
            for comment_data in data['comments']:
                # fix parent id
                parent_id = comment_data['parent']
                if parent_id == 'root':
                    parent_id = None

                comment = video.add_comment(
                    id=comment_data['id'],
                    parent_id=parent_id,
                    text=comment_data['text'],
                    likes=comment_data['like_count'] or 0,
                    channel_id=comment_data['author_id'],
                    channel_avatar_url=comment_data['author_thumbnail'],
                    timestamp=datetime.datetime.utcfromtimestamp(comment_data['timestamp']),
                    favorited=comment_data['is_favorited']
                )

                if comment.channel:
                    continue

                log(f"comment channel: {comment_data['author']} {comment_data['author_id']} {comment.channel} {comment.channel_id} {Channel.get(comment_data['author_id'])}")

                parse_channel('channel/' + comment.channel_id, ChannelStatus.QUEUED)

        log(f"parsed video details, got {len(video.comments)} comments")

    return True
