MIN_SUBSCRIBERS = 0
MAX_SUBSCRIBERS = 3000

BLOCK_NO_VIDEOS = False
MAX_VIDEOS = 300


def filter_about(about):
    if about['channel_follower_count'] > MAX_SUBSCRIBERS or about['channel_follower_count'] < MIN_SUBSCRIBERS:
        return True

    return False


def filter_videos(videos):
    num_videos = len(videos['entries'])

    if num_videos == 0 and BLOCK_NO_VIDEOS:
        return True

    if num_videos > MAX_VIDEOS:
        return True

    return False