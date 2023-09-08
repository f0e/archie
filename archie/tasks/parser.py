import time
from datetime import datetime, timedelta

import archie.database.database as db
from archie.config import Config
from archie.sources import youtube
from archie.utils import utils


def log(*args, **kwargs):
    utils.module_log("parse", "green", *args, **kwargs)


def parse(config: Config):
    sleeping = False

    while True:
        for archive_config in config.archives:
            archive = db.Archive.get(archive_config.name)

            # parse all manually added channels
            for channel_id in archive_config.channels:
                channel = db.Channel.get(channel_id, True)
                if channel:
                    if channel not in archive.channels:
                        # channel already added in another archive
                        archive.add_channel(channel, False)

                    continue

                youtube.parse_channel("channel/" + channel_id, archive_config, db.ChannelStatus.ACCEPTED)

            # parse all accepted channels (spider or db editing)
            while True:
                before_time = datetime.utcnow() - timedelta(hours=archive_config.updating.channel_update_gap_hours)
                channel = archive.get_next_of_status(db.ChannelStatus.ACCEPTED, before_time)
                if not channel:
                    break

                log(f"updating channel {channel.name} ({channel.id})")
                youtube.update_channel(channel, archive_config)

                log(f"finished parsing {channel.name} ({channel.id})")

            if not sleeping:
                log("finished parsing accepted channels, sleeping...")
                sleeping = True

            time.sleep(1)
