import time
from pathlib import Path

import click

import archie.api.api as api
from archie.config import CFG_PATH, Entity, load_config
from archie.services.base_download import rich_progress
from archie.services.base_service import BaseService
from archie.services.soundcloud import SoundCloudService
from archie.services.youtube import YouTubeService
from archie.utils import utils

# idk
service_list: list[BaseService] = [
    YouTubeService(),
    SoundCloudService(),
]

services = {}
for service in service_list:
    services[service.service_name.lower()] = service


@click.group()
def archie():
    pass


@archie.command()
@click.argument("archive_name", required=True)
def create(archive_name):
    """
    Creates a new archive
    """

    with load_config() as config:
        # check if name is duplicate
        if any(archive.name == archive_name for archive in config.archives):
            return utils.log(f"An archive already exists with the name '{archive_name}'.")

        # create new archive
        config.add_archive(archive_name)
        config.save()

    utils.log(f"Created archive '{archive_name}'. You can edit the archive settings at {CFG_PATH}.")
    utils.log(f"To add channels to the archive, use [dim]archie add-entity {archive_name}[/dim]")


@archie.command()
@click.argument("archive_name", required=True)
@click.argument("entity_name", required=True)
def add_entity(archive_name, entity_name):
    # TODO: Change name to something less verbose
    """
    Adds an entity to an archive
    """

    with load_config() as config:
        archive = utils.find(config.archives, lambda archive: archive.name == archive_name)
        if not archive:
            return utils.log(f"Archive '{archive_name}' not found.")

        # check if entity name is duplicate
        entity = utils.find(archive.entities, lambda entity: entity.name == entity_name)
        if entity:
            return utils.log(f"An entity named '{entity_name}' already exists in archive '{archive_name}'.")

        # create new entity
        archive.entities.append(Entity(name=entity_name))
        config.save()

    utils.log(f"Added entity '{entity_name}' to archive '{archive_name}'.")
    utils.log(f"To add accounts to the entity, use [dim]archie add-entity-account {entity_name} [service] [link][/dim]")


@archie.command()
@click.argument("archive_name", required=True)
@click.argument("entity_name", required=True)
@click.argument("service", required=True)
@click.argument("account", required=True)
def add_entity_account(archive_name, entity_name, service, account):
    # TODO: Change name to something less verbose
    """
    Add an account to an entity
    """

    if service not in services:
        return utils.log(f"Service not supported. Supported services: {', '.join(services.keys())}")

    with load_config() as config:
        archive = utils.find(config.archives, lambda archive: archive.name == archive_name)
        if not archive:
            return utils.log(f"Archive '{archive_name}' not found.")

        entity = utils.find(archive.entities, lambda entity: entity.name == entity_name)
        if not entity:
            return utils.log(f"Entity '{entity_name}' not found.")

        if not entity.add_account(services[service], account):
            return utils.log("Account not added")

        config.save()

    utils.log(f"Added account to entity '{entity_name}' in archive '{archive_name}'.")


@archie.command()
def run():
    """
    Runs archives
    """
    with load_config() as config:
        with rich_progress:
            if len(config.archives) == 0:
                return utils.log("No archives created, create one using [dim]create [archive name] [channel(s)][/dim]")

            for archive in config.archives:
                if not Path(archive.downloads.download_path).is_absolute():
                    return utils.log(
                        f"The download path '{archive.downloads.download_path}' specified in archive '{archive.name}' does not exist or is invalid. Please add a proper path and try again."
                    )

            for service_name, service in services.items():
                service.run(config)

            while True:
                # Twidles Thumbs
                time.sleep(0.5)


@archie.command()
def serve():
    api.run()


if __name__ == "__main__":
    archie()
