import archie.config as cfg


def filter_spider_channel(filters: cfg.SpiderFilterOptions, subscribers: int, verified: bool, num_videos: int):
    if subscribers > filters.max_subscribers or subscribers < filters.min_subscribers:
        return True

    if verified and filters.filter_verified:
        return True

    if (num_videos == 0 and filters.block_no_videos) or num_videos > filters.max_videos:
        return True

    # todo: filter livestreams. is it possible here or does it have to be done after getting full video info

    return False


def filter_video(video):
    return False
