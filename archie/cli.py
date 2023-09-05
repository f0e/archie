import click

from .database.database import database_connection
from .tasks import downloader, parser


@click.group()
def archie():
    pass


@archie.command()
@click.argument("channels", nargs=-1, required=True)
def create(channels):
    """
    Creates a new archive
    """
    print(channels)
    main_loop()


@archie.command()
def watch():
    """
    Watches archives
    """
    main_loop()


def main_loop():
    with database_connection():
        parser.init()
        parser.parse_accepted_channels()

        downloader.run()
