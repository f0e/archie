from utils.config import settings


def filter_channel(subscribers: int, verified: bool, num_videos: int):
    if subscribers > settings.max_subscribers or subscribers < settings.min_subscribers:
        return True

    if verified and settings.filter_verified:
        return True

    if (num_videos == 0 and settings.block_no_videos) or num_videos > settings.max_videos:
        return True

    # todo: filter livestreams. is it possible here or does it have to be done after getting full video info

    return False


def filter_video(video):
    return False
