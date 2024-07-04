import time
from pathlib import Path

import click

import archie.api.api as api
import archie.database.database as db
from archie.config import CFG_PATH, ArchiveConfig, Entity, load_config
from archie.services.base_download import rich_progress
from archie.services.youtube import YouTubeService
from archie.utils import utils

services = {
    "youtube": YouTubeService(),
}


@click.group()
def archie():
    pass


# def add_account_to_archive(config: Config, entity: Entity, service: BaseService, account: str) -> bool:
#     if validate_url(account):
#         account_link = account
#     else:
#         account_link = service.get_api.get_account_url_from_id(account)

#     account_id = service.get_api.get_account_id_from_url(account_link)
#     if not account_id:
#         return False

#     existing_account = utils.find(
#         entity.accounts, lambda account: account.service == service.get_service_name and account.id == account_id
#     )
#     if existing_account:
#         utils.log(f"Account already added to entity")
#         return False

#     entity.accounts.append(Account(service=service.get_service_name, id=account_id))
#     utils.log(f"Added account")

#     config.save()

#     return True


@archie.command()
@click.argument("archive_name", required=True)
def create(archive_name):
    """
    Creates a new archive
    """

    with db.connect():
        with load_config() as config:
            # check if name is duplicate
            if any(archive.name == archive_name for archive in config.archives):
                return utils.log(f"An archive already exists with the name '{archive_name}'.")

            # create new archive
            config.archives.append(ArchiveConfig(name=archive_name))
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

    with db.connect():
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

    with db.connect():
        with load_config() as config:
            archive = utils.find(config.archives, lambda archive: archive.name == archive_name)
            if not archive:
                return utils.log(f"Archive '{archive_name}' not found.")

            entity = utils.find(archive.entities, lambda entity: entity.name == entity_name)
            if not entity:
                return utils.log(f"Entity '{entity_name}' not found.")

            # if not add_account_to_archive(config, entity, services[service], account):
            #     return utils.log("Account not added")

    utils.log(f"Added account to entity '{entity_name}' in archive '{archive_name}'.")


@archie.command()
def run():
    """
    Runs archives
    """
    with db.connect():
        with load_config() as config:
            with rich_progress:
                if len(config.archives) == 0:
                    return utils.log("No archives created, create one using [dim]create [archive name] [channel(s)][/dim]")

                for archive in config.archives:
                    if not Path(archive.downloads.download_path).is_absolute():
                        return utils.log(
                            f"The download path '{archive.downloads.download_path}' specified in archive '{archive.name}' is not a valid path. Please add a proper path and try again."
                        )

                for service_name, service in services.items():
                    service.run(config)

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
