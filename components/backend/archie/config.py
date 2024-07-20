from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Tuple

import yaml
from pydantic import BaseModel

from archie import ARCHIE_PATH
from archie.services.base_service import BaseService
from archie.utils import utils

CFG_PATH = (
    ARCHIE_PATH / "config.yaml"
)  # fixed for now, if that changes add in a unique column to the archive table and handle that properly

TEMP_DL_PATH = ARCHIE_PATH / "temp-downloads"


class FilterOptions(BaseModel):
    parse_playlists: bool = True


class SpiderFilterOptions(BaseModel):
    min_subscribers: int = 0
    max_subscribers: int = 30000

    filter_verified: bool = False
    filter_livestreams: bool = True
    block_no_videos: bool = False
    max_videos: int = 300

    parse_playlists: bool = True


class YouTubeOptions(BaseModel):
    channel_update_gap_hours: int = 24
    playlist_update_gap_hours: int = 24
    video_update_gap_hours: int = 24 * 7


class SoundCloudOptions(BaseModel):
    user_update_gap_hours: int = 24
    track_update_gap_hours: int = 24 * 7


class DownloadOptions(BaseModel):
    download_path: str = "~/archie-downloads"


class SpiderOptions(BaseModel):
    enabled: bool = False
    filters: SpiderFilterOptions = SpiderFilterOptions()


class Account(BaseModel):
    service: str
    id: str | int


class Entity(BaseModel):
    name: str
    accounts: list[Account] = []

    # TODO: more fields, copy from rym?

    def add_account(self, service: BaseService, account: str) -> bool:
        if utils.validate_url(account):
            account_link = account
        else:
            account_link = service.get_account_url_from_id(account)
            if not account_link:
                utils.log("Invalid account id")
                return False

        account_id = service.get_account_id_from_url(account_link)
        if not account_id:
            return False

        existing_account = utils.find(
            self.accounts, lambda account: account.service == service.service_name and account.id == account_id
        )
        if existing_account:
            utils.log("Account already added to entity")
            return False

        self.accounts.append(Account(service=service.service_name, id=account_id))

        return True


class ServiceOptions(BaseModel):
    youtube: YouTubeOptions = YouTubeOptions()
    soundcloud: SoundCloudOptions = SoundCloudOptions()


class ArchiveConfig(BaseModel):
    name: str
    entities: list[Entity] = []

    # filters: FilterOptions = FilterOptions()
    downloads: DownloadOptions = DownloadOptions()
    # spider: SpiderOptions = SpiderOptions()


class Config(BaseModel):
    archives: list[ArchiveConfig] = []
    services: ServiceOptions = (
        ServiceOptions()
    )  # TODO: move this back to archive-specific, but it makes things a bit more complicated in queries

    def dump(self):
        return self.model_dump()

    def save(self, path: Path = CFG_PATH):
        with path.open("w") as f:
            yaml.dump(self.dump(), f, Dumper=utils.PrettyDumper, sort_keys=False)

    @staticmethod
    def load(path: Path = CFG_PATH):
        if not path.exists() or path.stat().st_size == 0:
            Config().save()

        with path.open("r") as f:
            yaml_data = yaml.safe_load(f)

            if not isinstance(yaml_data, dict):
                raise ValueError("YAML data is not a dictionary")

            return Config(**yaml_data)

    def add_archive(self, archive_name: str):
        self.archives.append(ArchiveConfig(name=archive_name))

    def find_archives_with_account(self, service: str, id: str) -> Iterator[ArchiveConfig]:
        for archive in self.archives:
            for entity in archive.entities:
                for account in entity.accounts:
                    if account.service == service and account.id == id:
                        yield archive

    def get_accounts(self, service: str) -> Iterator[Tuple[Account, Entity, ArchiveConfig]]:
        for archive in self.archives:
            for entity in archive.entities:
                for account in entity.accounts:
                    if account.service == service:
                        yield account, entity, archive


@contextmanager
def load_config():
    config: Config | None = None

    try:
        config = Config.load()

        # config might be missing or have extra variables, save after validating
        # todo: i know if you just created a config for the first time this will save pointlessly but idc
        config.save()

        yield config
    finally:
        pass
        ### this is actually bad because the user might be modifying the config on their own and this will overwrite it even if nothing changed.
        ### instead just config.save every time something changes
        # if config:
        #     config.save()
