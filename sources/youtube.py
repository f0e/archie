import json
import datetime
from typing import Dict
import yt_dlp
import threading

from database.database import Channel, ChannelStatus, Video, VideoComment
from . import filter


def log(message):
    print("[youtube] " + message)


def debug_write(yt, data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(yt.sanitize_info(data)))


def update_channel(channel: Channel) -> Channel | None:
    return parse_channel('channel/' + channel.id, channel.status)


def parse_channel(channelLink: str, status: ChannelStatus) -> Channel | None:
    # adds a channel to the database. will filter out unwanted channels.
    # only adds basic information on /about page

    ydl_opts = {
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        about = yt.extract_info(f'https://www.youtube.com/{channelLink}/about', download=False)

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

        if filter.filter_channel_about(subscribers, verified):
            # todo: what to do when the channel's already been added
            return None

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

        parse_videos(channel)  # it takes like no time so just do it for all channels

        if channel.status == ChannelStatus.ACCEPTED:
            for video in channel.videos:
                if not video.fully_parsed:
                    # video hasn't been parsed yet
                    parse_video_details(video)

        log(f"parsed channel {channel.name} ({channel.id})")

        channel.set_updated()

    return channel


def parse_videos(channel: Channel):
    # updates a channel's videos, playlists, etc.

    ydl_opts = {
        # don't get videos, just get the data available from the /videos page
        'extract_flat': True,
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        try:
            data = yt.extract_info(f'https://www.youtube.com/channel/{channel.id}/videos', download=False)
        except yt_dlp.utils.DownloadError as e:
            if 'This channel does not have a videos tab' in e.msg:
                log(f"channel {channel.name} has no videos, skipping video parsing ({channel.id})")
            else:
                log(f"misc error parsing channel {channel.name} videos, skipping video parsing")

            return None

        num_videos = len(data['entries'])

        if filter.filter_channel_videos(num_videos):
            # todo: what to do when the channel's already been added
            pass

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

            log(f"parsed basic video info for {video.title} in channel {channel.id} ({video.id})")

    return channel.videos


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

        print(video.availability)

        if video.availability == "public" or video.availability == "unlisted":
            threading.Thread(download_video(video)).start()

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

                if Channel.get(comment.channel_id):
                    continue

                # new channel, add to queue
                parse_channel('channel/' + comment.channel_id, ChannelStatus.QUEUED)

        video.set_updated()

        log(f"parsed video details, got {len(video.comments)} comments")

    return True


def download_video(video: Video):
    ydl_opts = {
        # don't redownload videos
        'nooverwrites': True,

        # bypass geographic restrictions
        'geo_bypass': True,

        # don't download livestreams
        # 'match_filter': '!is_live',

        'format': 'bv*+ba',

        'postprocessors': [
            {'key': 'FFmpegMetadata', 'add_metadata': True, },
            {'key': 'EmbedThumbnail', 'already_have_thumbnail': False, }],

        # output folder
        'outtmpl': f'{video.channel_id}/{video.id}'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        error_code = yt.download(f'https://www.youtube.com/watch?v={video.id}')
