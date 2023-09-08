from contextlib import contextmanager
from pathlib import Path

import yaml
from pydantic import BaseModel

from archie import ARCHIE_PATH
from archie.database import database as db
from archie.utils.utils import PrettyDumper

CFG_PATH = (
    ARCHIE_PATH / "config.yaml"
)  # fixed for now, if that changes add in a unique column to the archive table and handle that properly

TEMP_DL_PATH = ARCHIE_PATH / "temp-downloads"


class FilterOptions(BaseModel):
    pass


class SpiderFilterOptions(BaseModel):
    min_subscribers: int = 0
    max_subscribers: int = 30000

    filter_verified: bool = False
    filter_livestreams: bool = True

    block_no_videos: bool = False
    max_videos: int = 300


class UpdateOptions(BaseModel):
    channel_update_gap_hours: int = 24
    video_update_gap_hours: int = 24 * 7


class DownloadOptions(BaseModel):
    download_path: str = "./downloads"


class SpiderOptions(BaseModel):
    enabled: bool = False
    filters: SpiderFilterOptions = SpiderFilterOptions()


class ArchiveConfig(BaseModel):
    name: str
    channels: list[str]

    # filters: FilterOptions = FilterOptions()
    updating: UpdateOptions = UpdateOptions()
    downloads: DownloadOptions = DownloadOptions()
    spider: SpiderOptions = SpiderOptions()


class Config(BaseModel):
    archives: list[ArchiveConfig] = []

    def dump(self):
        return self.model_dump()

    def save(self, path: Path = CFG_PATH):
        with path.open("w") as f:
            yaml.dump(self.dump(), f, Dumper=PrettyDumper, sort_keys=False)

    @staticmethod
    def load(path: Path = CFG_PATH):
        if not path.exists() or path.stat().st_size == 0:
            Config().save()

        with path.open("r") as f:
            yaml_data = yaml.safe_load(f)

            if not isinstance(yaml_data, dict):
                raise ValueError("YAML data is not a dictionary")

            return Config(**yaml_data)


@contextmanager
def load_config():
    config: Config | None = None

    try:
        if not db.initialised:
            raise Exception("Database not initialised")

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
