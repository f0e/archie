MIN_SUBSCRIBERS = 0
MAX_SUBSCRIBERS = 10000
FILTER_VERIFIED = False

BLOCK_NO_VIDEOS = False
MAX_VIDEOS = 300
FILTER_LIVESTREAMS = True


def filter_channel(subscribers: int, verified: bool, num_videos: int):
    if subscribers > MAX_SUBSCRIBERS or subscribers < MIN_SUBSCRIBERS:
        return True

    if verified and FILTER_VERIFIED:
        return True

    if (num_videos == 0 and BLOCK_NO_VIDEOS) or num_videos > MAX_VIDEOS:
        return True

    # todo: filter livestreams. is it possible here or does it have to be done after getting full video info

    return False


def filter_video(video):
    return False
