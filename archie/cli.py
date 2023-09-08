import threading
import time

import click
from colorama import Fore, Style

import archie.database.database as db
from archie.config import ArchiveConfig, Config, load_config
from archie.sources import youtube
from archie.tasks import downloader, parser
from archie.utils import utils
from archie.utils.utils import validate_url


@click.group()
def archie():
    pass


def add_channels_to_archive(config: Config, name: str, channels: list[str]) -> bool:
    # check if name is a link
    if validate_url(name):
        if not click.prompt("Archive name is a URL, are you sure you want to continue? (y/n)", type=bool):
            return False

    # todo: check if name is a youtube id

    utils.log(f"Validating {len(channels)} channels...")

    # get existing archive (if there is one)
    archive = utils.find(config.archives, lambda archive: archive.name == name)

    # validate channels and get ids
    channel_ids: list[str] = []

    for channel in channels:
        if not validate_url(channel):
            channelLink = f"https://youtube.com/channel/{channel}"
        else:
            channelLink = channel

        data = youtube.get_data(channelLink)
        channel_id = data["channel_id"]

        if channel_id in channel_ids or (archive and channel_id in archive.channels):
            utils.log(f"Skipping duplicate channel {channel}")
            continue

        channel_ids.append(channel_id)

    if archive:
        # add channels to existing archive
        archive.channels = archive.channels + channel_ids
    else:
        # create new archive
        config.archives.append(ArchiveConfig(name=name, channels=channel_ids))

    config.save()

    return True


@archie.command()
@click.argument("name", required=False)
@click.argument("channels", nargs=-1, required=False)
def create(name, channels):
    """
    Creates a new archive
    """

    def print_error_and_examples(msg: str):
        utils.log(
            msg + " To create an archive, enter a name and a list of YouTube channel links or IDs after the create command."
        )
        utils.log(
            f"e.g. {Fore.LIGHTBLACK_EX}archie create my-archive https://youtube.com/@Jerma985 https://youtube.com/@2ndJerma{Style.RESET_ALL}"
        )
        utils.log(
            f"or {Fore.LIGHTBLACK_EX}archie create my-archive UCK3kaNXbB57CLcyhtccV_yw UCL7DDQWP6x7wy0O6L5ZIgxg{Style.RESET_ALL}"
        )

    if not name:
        return print_error_and_examples("No name provided.")

    if len(channels) == 0:
        return print_error_and_examples("No channels provided.")

    with db.connect():
        with load_config() as config:
            # check if name is duplicate
            if any(archive.name == name for archive in config.archives):
                return utils.log(f"An archive already exists with the name '{name}'.")

            if not add_channels_to_archive(config, name, channels):
                return utils.log("Cancelled archive creation.")

    utils.log(f"Created archive '{name}'. You can edit the archive settings at {config.CFG_PATH}.")
    utils.log(f"To run the archive, use {Fore.LIGHTBLACK_EX}archie run{Style.RESET_ALL}")


@archie.command()
@click.argument("name", required=False)
@click.argument("channels", nargs=-1, required=False)
def add(name, channels):
    """
    Adds channels to an existing archive
    """

    def print_error_and_examples(msg: str):
        utils.log(
            msg + " To add channels to an archive, enter a name and a list of YouTube channel links or IDs after the add command."
        )
        utils.log(
            f"e.g. {Fore.LIGHTBLACK_EX}archie add my-archive https://youtube.com/@Jerma985 https://youtube.com/@2ndJerma{Style.RESET_ALL}"
        )
        utils.log(
            f"or {Fore.LIGHTBLACK_EX}archie add my-archive UCK3kaNXbB57CLcyhtccV_yw UCL7DDQWP6x7wy0O6L5ZIgxg{Style.RESET_ALL}"
        )

    if not name:
        return print_error_and_examples("No name provided.")

    if len(channels) == 0:
        return print_error_and_examples("No channels provided.")

    with db.connect():
        with load_config() as config:
            # check if name is not duplicate
            if not any(archive.name == name for archive in config.archives):
                return utils.log(f"Archive '{name}' not found.")

            if not add_channels_to_archive(config, name, channels):
                return utils.log("Cancelled archive creation.")

    utils.log(f"Added channels to archive '{name}'. You can edit the archive settings at {config.CFG_PATH}.")
    utils.log(f"To run the archive, use {Fore.LIGHTBLACK_EX}archie run{Style.RESET_ALL}")


@archie.command()
def run():
    """
    Runs archives
    """
    with db.connect():
        with load_config() as config:
            with youtube.rich_progress:
                if len(config.archives) == 0:
                    return utils.log(
                        "No archives created, create one using {Fore.LIGHTBLACK_EX}create [archive name] [channel(s)]{Style.RESET_ALL}"
                    )

                downloader.init()

                for i in range(5):
                    threading.Thread(target=downloader.download_videos, args=(config,), daemon=True).start()

                threading.Thread(target=parser.parse, args=(config,), daemon=True).start()

                while True:
                    # Twidles Thumbs
                    time.sleep(0.5)


@archie.group()
def spider():
    """
    Manage the spider, filter found channels, etc.
    """
    pass


@spider.command()
@click.argument("name", required=False)
def filter(name: str):
    """
    Filter channels found by the spider
    """
    # with db.connect():
    #     with load_config() as config:
    #         if len(config.archives) == 0:
    #             return utils.log(
    #                 "No archives created, create one using {Fore.LIGHTBLACK_EX}create [archive name] [channel(s)]{Style.RESET_ALL}"
    #             )

    #         # check archive name
    #         archive_config = utils.find(config.archives, lambda archive: archive.name == name)
    #         if not archive_config:
    #             return utils.log(f"Archive '{name}' not found.")

    #         archive = db.Archive.get(archive_config.name)

    #         queue_index = 0
    #         last_action = None

    #         def can_move(diff: int):
    #             nonlocal queue_index

    #             if diff < 0:
    #                 return queue_index + diff >= 0
    #             else:
    #                 return archive.get_queued_channel(queue_index + diff)

    #         def queue_move(diff: int):
    #             nonlocal queue_index, last_action

    #             if not can_move(diff):
    #                 return

    #             queue_index += diff
    #             last_action = f"Skipped {'forward' if diff > 0 else 'back'}" + (f" {abs(diff)} channels" if abs(diff) > 1 else "")

    #         while True:
    #             channel = archive.get_queued_channel(queue_index)

    #             def queue_set_status(new_status: db.ChannelStatus):
    #                 nonlocal channel, queue_index, last_action

    #                 channel.set_status(new_status)

    #                 status_names = {
    #                     db.ChannelStatus.ACCEPTED: "Accepted",
    #                     db.ChannelStatus.REJECTED: "REJECTED",
    #                 }

    #                 last_action = f"{status_names[new_status]} {channel.name}"

    #                 # channel status changing means we move forward one, so move back however much we have to (should always be 1)
    #                 while not archive.get_queued_channel(queue_index):
    #                     queue_index -= 1

    #             video_count = len(channel.videos)

    #             lines = [
    #                 channel.name,
    #                 f"{channel.subscribers} subscriber{'s' if channel.subscribers != 1 else ''}, {video_count} video{'s' if video_count != 1 else ''}",
    #                 f"https://youtube.com/channel/{channel.id}",
    #                 "",
    #                 Fore.LIGHTGREEN_EX + "[Y] Accept" + Style.RESET_ALL,
    #                 Fore.LIGHTRED_EX + "[N] Reject" + Style.RESET_ALL,
    #                 "[Q] Quit",
    #                 (
    #                     ("" if can_move(-1) else Fore.LIGHTBLACK_EX)
    #                     + "[A] Previous "
    #                     + Style.RESET_ALL
    #                     + ("" if can_move(1) else Fore.LIGHTBLACK_EX)
    #                     + "[D] Next "
    #                     + Style.RESET_ALL
    #                 ),
    #             ]

    #             if last_action is not None:
    #                 lines.append(last_action)

    #             utils.print_multiline_replacing(lines)

    #             key = click.getchar()
    #             match key:
    #                 # moving
    #                 case "a":
    #                     queue_move(-1)

    #                 case "d":
    #                     queue_move(1)

    #                 # accept/rejecting
    #                 case "y":
    #                     queue_set_status(db.ChannelStatus.ACCEPTED)

    #                 case "n":
    #                     queue_set_status(db.ChannelStatus.REJECTED)

    #                 # quitting
    #                 case "q":
    #                     break

    #         utils.log("Quitting.")
