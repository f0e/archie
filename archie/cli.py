import threading
import time
from pathlib import Path

import click

import archie.api.api as api
import archie.database.database as db
from archie.config import CFG_PATH, ArchiveConfig, Config, load_config
from archie.sources import youtube
from archie.tasks import downloader, parser
from archie.utils import utils
from archie.utils.utils import validate_url


@click.group()
def archie():
    pass


def add_channels_to_archive(config: Config, archive_name: str, channels: list[str]) -> bool:
    # check if name is a link
    if validate_url(archive_name):
        if not click.prompt("Archive name is a URL, are you sure you want to continue? (y/n)", type=bool):
            return False

    # todo: check if name is a youtube id

    utils.log(f"Validating {len(channels)} channels...")

    # get existing archive
    archive = utils.find(config.archives, lambda archive: archive.name == archive_name)
    if not archive:
        utils.log(f"Failed to find archive {archive_name}")
        return False

    # validate channels and get ids
    channel_ids: list[str] = []

    for channel in channels:
        if not validate_url(channel):
            channelLink = f"https://youtube.com/channel/{channel}"
        else:
            channelLink = channel

        try:
            data = youtube.get_data(channelLink)
            channel_id = data["channel_id"]

            if channel_id in channel_ids or channel_id in archive.channels:
                utils.log(f"Skipping duplicate channel {channel}")
                continue

            channel_ids.append(channel_id)
            utils.log(f"Added channel {data['channel']}")
        except Exception:
            utils.log(f"Failed to fetch channel {channelLink}, skipping.")

    if len(channel_ids) == 0:
        utils.log("No valid channels were found.")
        return False

    # add channels to existing archive
    archive.channels = archive.channels + channel_ids

    config.save()

    return True


@archie.command()
@click.argument("name", required=False)
def create(name):
    """
    Creates a new archive
    """

    def print_error_and_examples(msg: str):
        utils.log(msg + " To create an archive, enter a name.")
        utils.log("e.g. [dim]archie create my-archive[/dim]")

    if not name:
        return print_error_and_examples("No name provided.")

    with db.connect():
        with load_config() as config:
            # check if name is duplicate
            if any(archive.name == name for archive in config.archives):
                return utils.log(f"An archive already exists with the name '{name}'.")

            # create new archive
            config.archives.append(ArchiveConfig(name=name))
            config.save()

    utils.log(f"Created archive '{name}'. You can edit the archive settings at {CFG_PATH}.")
    utils.log(f"To add channels to the archive, use [dim]archie add {name}[/dim]")


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
        utils.log("e.g. [dim]archie add my-archive https://youtube.com/@Jerma985 https://youtube.com/@2ndJerma[/dim]")
        utils.log("or [dim]archie add my-archive UCK3kaNXbB57CLcyhtccV_yw UCL7DDQWP6x7wy0O6L5ZIgxg[/dim]")

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
                return utils.log("Cancelled adding channel.")

    utils.log(f"Added channels to archive '{name}'.")
    utils.log("To run the archive, use [dim]archie run[/dim]")


@archie.command()
def run():
    """
    Runs archives
    """
    with db.connect():
        with load_config() as config:
            with youtube.rich_progress:
                if len(config.archives) == 0:
                    return utils.log("No archives created, create one using [dim]create [archive name] [channel(s)][/dim]")

                for archive in config.archives:
                    if not Path(archive.downloads.download_path).is_absolute():
                        return utils.log(
                            f"The download path '{archive.downloads.download_path}' specified in archive '{archive.name}' is not a valid path. Please add a proper path and try again."
                        )

                downloader.init()

                for i in range(5):
                    threading.Thread(target=downloader.download_videos, args=(config,), daemon=True).start()

                threading.Thread(target=parser.parse, args=(config,), daemon=True).start()

                while True:
                    # Twidles Thumbs
                    time.sleep(0.5)


@archie.command()
def serve():
    api.run()


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
    #                 "No archives created, create one using [dim]create [archive name] [channel(s)][/dim]"
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


if __name__ == "__main__":
    archie()
