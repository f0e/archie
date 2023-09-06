import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import yt_dlp  # type: ignore
from colorama import Fore, Style

import archie.config as cfg
from archie import ARCHIE_PATH
from archie.database.database import Archive, Channel, ChannelStatus, Video
from archie.sources import filter
from archie.utils import utils

in_spider = False


def log(*args, **kwargs):
    if not in_spider:
        utils.safe_log("youtube", "red", *args, **kwargs)
    else:
        utils.safe_log("youtube (spider)", "magenta", *args, **kwargs)


def debug_write(yt, data, filename):
    with open(f"{filename}.json", "w") as out_file:
        out_file.write(json.dumps(yt.sanitize_info(data)))


def get_data(channelLink: str):
    ydl_opts = {
        "extract_flat": True,  # don't parse individual videos, just get the data available from the /videos page
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        return yt.extract_info(channelLink, download=False, process=False)


def update_channel(channel: Channel, archive: cfg.ArchiveConfig) -> Channel | None:
    return parse_channel("channel/" + channel.id, archive, channel.status)


def parse_channel(channel_link: str, archive_config: cfg.ArchiveConfig, status: ChannelStatus, from_spider: bool = False) -> Channel | None:
    # adds a channel to the database. will filter out unwanted channels.

    ydl_opts = {
        "extract_flat": True,  # don't parse individual videos, just get the data available from the /videos page
        "quiet": True,
    }

    log(f"parsing channel {channel_link}")

    archive = Archive.get(archive_config.name)

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        try:
            data = yt.extract_info(f"https://www.youtube.com/{channel_link}/videos", download=False)
        except yt_dlp.utils.DownloadError as e:
            if "This channel does not have a videos tab" in e.msg:
                log(f"channel has no videos, fetching about page instead ({channel_link})")
            else:
                log(f"misc parsing error, skipping parsing ({channel_link})")
                return None

            try:
                data = yt.extract_info(f"https://www.youtube.com/{channel_link}/about", download=False)
            except yt_dlp.utils.DownloadError as e:
                if "This channel does not have a about tab" in e.msg:
                    log("channel doesn't have an about page? skipping")
                    return None
                else:
                    raise e

        # get avatar and banner
        avatar_url = None
        banner_url = None
        for image in data["thumbnails"]:
            if image["id"] == "avatar_uncropped":
                avatar_url = image["url"]
            elif image["id"] == "banner_uncropped":
                banner_url = image["url"]

        verified = False
        if "channel_is_verified" in data:
            verified = data["channel_is_verified"]

        subscribers = data["channel_follower_count"] or 0

        num_videos = len(data["entries"])

        if from_spider:
            if filter.filter_spider_channel(archive_config.spider.filters, subscribers, verified, num_videos):
                # todo: what to do when the channel's already been added?
                # todo: store filtered channels in db so they don't get checked again? and it'll also store their
                #       info in case you change your mind on filter settings?
                # todo: go back to parsing /about for filtering???
                log("filtered channel")
                return None

        channel = archive.add_channel(
            Channel.create_or_update(
                status=status,
                id=data["channel_id"],
                name=data["channel"],
                avatar_url=avatar_url,
                banner_url=banner_url,
                description=data["description"],
                subscribers=subscribers,
                tags_list=data["tags"],
                verified=verified,
            ),
            from_spider,
        )

        log(f"parsed channel {channel.name} ({channel.id})")

        for entry in data["entries"]:
            video = channel.add_or_update_video(
                id=entry["id"],
                title=entry["title"],
                thumbnail_url=entry["thumbnails"][0]["url"],  # placeholder, get better quality thumbnail in parse_video_details
                description=entry["description"],
                duration=entry["duration"],
                availability=entry["availability"],
                views=entry["view_count"],
            )

            if channel.status == ChannelStatus.ACCEPTED:
                video_min_update_time = datetime.utcnow() - timedelta(hours=archive_config.updating.video_update_gap_hours)
                if not video.fully_parsed or video.update_time <= video_min_update_time:
                    parse_video_details(video, archive_config)

        log(f"parsed {len(channel.videos)} videos in channel {channel.name} ({channel.id})")

        channel.set_updated()

    return channel


def parse_video_details(video: Video, archive_config: cfg.ArchiveConfig):
    # gets all info and commenters for a video

    ydl_opts = {
        "getcomments": True,
        "quiet": True,
    }

    log(f"parsing video {video.title} by {video.channel.name} ({video.id})")

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        data = yt.extract_info(f"https://www.youtube.com/watch?v={video.id}", download=False)

        if filter.filter_video(data):
            # todo: what to do when the video's already been added
            pass

        video.update_details(
            thumbnail_url=data["thumbnail"],
            categories_list=data["categories"],
            tags_list=data["tags"],
            availability=data["availability"],
            timestamp=datetime.utcfromtimestamp(data["epoch"]),
        )

        if data["comments"]:
            for comment_data in data["comments"]:
                # fix parent id
                parent_id = comment_data["parent"]
                if parent_id == "root":
                    parent_id = None

                comment = video.add_comment(
                    id=comment_data["id"],
                    parent_id=parent_id,
                    text=comment_data["text"],
                    likes=comment_data["like_count"] or 0,
                    channel_id=comment_data["author_id"],
                    channel_avatar_url=comment_data["author_thumbnail"],
                    timestamp=datetime.utcfromtimestamp(comment_data["timestamp"]),
                    favorited=comment_data["is_favorited"],
                )

                if comment.channel:
                    continue

                if archive_config.spider.enabled:
                    # new channel, add to queue
                    global in_spider
                    in_spider = True
                    parse_channel("channel/" + comment.channel_id, archive_config, ChannelStatus.QUEUED, from_spider=True)
                    in_spider = False

        video.set_updated()

        log(f"parsed video details, got {len(video.comments)} comments")

    return True


class VideoProgress:
    filename: str
    tmpfilename: str
    downloaded_bytes: int
    total_bytes: int | None
    total_bytes_estimate: int | None
    elapsed: int
    eta: int
    speed: float
    fragment_index: int | None
    fragment_count: int | None

    def __init__(self, data):
        self.filename = data.get("filename")
        self.tmpfilename = data.get("tmpfilename")
        self.downloaded_bytes = data.get("downloaded_bytes")
        self.total_bytes = data.get("total_bytes")
        self.total_bytes_estimate = data.get("total_bytes_estimate")
        self.elapsed = data.get("elapsed")
        self.eta = data.get("eta")
        self.speed = data.get("speed")
        self.fragment_index = data.get("fragment_index")
        self.fragment_count = data.get("fragment_count")


downloads: dict[str, VideoProgress] = dict()
total_speeds: list[int] = []
process_lock = threading.Lock()


def progress_hooks(data):
    with process_lock:
        match data["status"]:
            case "finished":
                video_id = data["info_dict"]["id"]
                if video_id in downloads:
                    del downloads[video_id]

            case "downloading":
                video_id = data["info_dict"]["id"]
                downloads[video_id] = VideoProgress(data)

        total_speed = 0

        messages = []
        for id, download in downloads.items():
            percent = 0

            if download.total_bytes:
                percent = download.downloaded_bytes / download.total_bytes

            messages.append(f"{Fore.LIGHTBLACK_EX}{id}:{Style.RESET_ALL} {percent*100:.2f}%")

            if download.speed:
                total_speed += download.speed

        total_speeds.insert(0, total_speed)
        del total_speeds[50:]

        average_speed = sum(total_speeds) / len(total_speeds)

        utils.print_progress(f"{len(downloads)} downloads ({average_speed/1000000:.2f} MB/s) " + ", ".join(messages))


@dataclass
class DownloadedVideo:
    path: Path
    format: str


def download_video(video: Video, download_folder: Path) -> DownloadedVideo:
    # returns the downloaded format

    temp_dl_path = ARCHIE_PATH / "temp-downloads"

    ydl_opts = {
        "progress_hooks": [progress_hooks],
        "quiet": True,
        "noprogress": True,
        # don't redownload videos
        "nooverwrites": True,
        # bypass geographic restrictions
        "geo_bypass": True,
        # write mkv files (prevent webm warning, it just uses mkv anyway)
        "merge_output_format": "mkv",
        # don't download livestreams
        # 'match_filter': '!is_live',
        "writethumbnail": True,
        "format": "bv*+ba",
        "postprocessors": [
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
            {
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            },
        ],
        # output folder
        "outtmpl": str(temp_dl_path.expanduser() / "%(channel_id)s/%(id)s.f%(format_id)s.%(ext)s"),
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        data = yt.extract_info(f"https://www.youtube.com/watch?v={video.id}", download=True)
        download_data = data["requested_downloads"][0]

        # get just the download path, not the stuff before it. so c:\...\temp-downloads\channel\video.mkv just becomes channel\video.mkv
        downloaded_path = Path(download_data["filepath"])
        relative_path = downloaded_path.relative_to(temp_dl_path)

        # build proper download path
        final_path = download_folder / relative_path

        if final_path.exists():
            log("video already exists? skipping")
        else:
            # move completed download
            final_path.parent.mkdir(parents=True, exist_ok=True)
            downloaded_path.rename(final_path)

        # # delete temp folder
        # shutil.rmtree(temp_dl_path)

        return DownloadedVideo(
            path=final_path,
            format=download_data["format_id"],
        )
