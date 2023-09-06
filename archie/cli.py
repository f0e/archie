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

    click.echo(f"Validating {len(channels)} channels...")

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
            click.echo(f"Skipping duplicate channel {channel}")
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
        click.echo(msg + " To create an archive, enter a name and a list of YouTube channel links or IDs after the create command.")
        click.echo(f"e.g. {Fore.LIGHTBLACK_EX}archie create my-archive https://youtube.com/@Jerma985 https://youtube.com/@2ndJerma{Style.RESET_ALL}")
        click.echo(f"or {Fore.LIGHTBLACK_EX}archie create my-archive UCK3kaNXbB57CLcyhtccV_yw UCL7DDQWP6x7wy0O6L5ZIgxg{Style.RESET_ALL}")

    if not name:
        return print_error_and_examples("No name provided.")

    if len(channels) == 0:
        return print_error_and_examples("No channels provided.")

    with db.connect():
        with load_config() as config:
            # check if name is duplicate
            if any(archive.name == name for archive in config.archives):
                return click.echo(f"An archive already exists with the name '{name}'.")

            if not add_channels_to_archive(config, name, channels):
                return click.echo("Cancelled archive creation.")

    click.echo(f"Created archive '{name}'. You can edit the archive settings at {config.CFG_PATH}.")
    click.echo(f"To run the archive, use {Fore.LIGHTBLACK_EX}archie run{Style.RESET_ALL}")


@archie.command()
@click.argument("name", required=False)
@click.argument("channels", nargs=-1, required=False)
def add(name, channels):
    """
    Adds channels to an existing archive
    """

    def print_error_and_examples(msg: str):
        click.echo(msg + " To add channels to an archive, enter a name and a list of YouTube channel links or IDs after the add command.")
        click.echo(f"e.g. {Fore.LIGHTBLACK_EX}archie add my-archive https://youtube.com/@Jerma985 https://youtube.com/@2ndJerma{Style.RESET_ALL}")
        click.echo(f"or {Fore.LIGHTBLACK_EX}archie add my-archive UCK3kaNXbB57CLcyhtccV_yw UCL7DDQWP6x7wy0O6L5ZIgxg{Style.RESET_ALL}")

    if not name:
        return print_error_and_examples("No name provided.")

    if len(channels) == 0:
        return print_error_and_examples("No channels provided.")

    with db.connect():
        with load_config() as config:
            # check if name is not duplicate
            if not any(archive.name == name for archive in config.archives):
                return click.echo(f"Archive '{name}' not found.")

            if not add_channels_to_archive(config, name, channels):
                return click.echo("Cancelled archive creation.")

    click.echo(f"Added channels to archive '{name}'. You can edit the archive settings at {config.CFG_PATH}.")
    click.echo(f"To run the archive, use {Fore.LIGHTBLACK_EX}archie run{Style.RESET_ALL}")


@archie.command()
def run():
    """
    Runs archives
    """
    with db.connect():
        with load_config() as config:
            if len(config.archives) == 0:
                return click.echo("No archives created, create one using {Fore.LIGHTBLACK_EX}create [archive name] [channel(s)]{Style.RESET_ALL}")

            downloader.check_downloads()

            for i in range(5):
                threading.Thread(target=downloader.download_videos, args=(config,), daemon=True).start()

            threading.Thread(target=parser.parse, args=(config,), daemon=True).start()

            while True:
                # Twidles Thumbs
                time.sleep(0.5)
