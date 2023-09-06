import threading
import time

import click

import archie.archie as arch
import archie.database.database as db
from archie.sources import youtube
from archie.tasks import downloader, parser
from archie.utils.utils import validate_url


@click.group()
def archie():
    pass


@archie.command()
@click.argument("name", required=False)
@click.argument("channels", nargs=-1, required=False)
def create(name, channels):
    """
    Creates a new archive
    """

    def print_error_and_examples(msg: str):
        click.echo(msg + " To create an archive, enter a name and a list of YouTube channel links or IDs after the create command.")
        click.echo("e.g. " + click.style("archie create my-archive https://youtube.com/@Jerma985 https://youtube.com/@2ndJerma", fg="cyan"))
        click.echo("or " + click.style("archie create my-archive UCK3kaNXbB57CLcyhtccV_yw UCL7DDQWP6x7wy0O6L5ZIgxg", fg="cyan"))

    if not name:
        return print_error_and_examples("No name provided.")

    if len(channels) == 0:
        return print_error_and_examples("No channels provided.")

    with db.database_connection():
        with arch.load_config() as config:
            # check if name is duplicate
            if any(archive.name == name for archive in config.archives):
                return click.echo(f"An archive already exists with the name '{name}'.")

            # check if name is a link
            if validate_url(name):
                if not click.prompt("Archive name is a URL, are you sure you want to continue? (y/n)", type=bool):
                    return False

            click.echo(f"Validating {len(channels)} channels...")

            # validate channels and get ids
            channelIds: list[str] = []

            for channel in channels:
                if not validate_url(channel):
                    channelLink = "https://youtube.com/channel/{channel}"
                else:
                    channelLink = channel

                data = youtube.get_data(channelLink)
                channelIds.append(data["channel_id"])

            config.archives.append(arch.ArchiveConfig(name=name, channels=channelIds))
            config.save()

    click.echo(f"Created archive '{name}'. You can edit the archive settings at {arch.CFG_PATH}.")
    click.echo("To run the archive, use " + click.style("archie run", fg="cyan"))


@archie.command()
def run():
    """
    Runs archives
    """
    with db.database_connection():
        with arch.load_config() as config:
            if len(config.archives) == 0:
                return click.echo("No archives created, create one using " + click.style("archie create [archive name] [channel(s)]", fg="cyan"))

            threading.Thread(target=downloader.download_videos, daemon=True).start()
            threading.Thread(target=parser.parse, args=(config,), daemon=True).start()

            while True:
                # Twidles Thumbs
                time.sleep(0.5)
