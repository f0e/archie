import json

from pathlib import Path
import os

from dacite import from_dict

from pydantic import TypeAdapter
from pydantic.dataclasses import dataclass

CFG_PATH = Path('config.json')


@dataclass
class Config():
    archie_path: str = os.path.join(Path.home(), "archie")

    min_subscribers: int = 0
    max_subscribers: int = 30000

    filter_verified: bool = False
    filter_livestreams: bool = True

    block_no_videos: bool = False
    max_videos: int = 300

    channel_update_gap_hours: int = 24
    video_update_gap_hours: int = 24 * 7

    def to_json(self):
        return json.loads(TypeAdapter(Config).dump_json(self))


def save_cfg(cfg: Config):
    with CFG_PATH.open('w') as f:
        json.dump(cfg.to_json(), f, indent=2)


def load_cfg():
    if not CFG_PATH.exists() or CFG_PATH.stat().st_size == 0:
        save_cfg(Config())

    with CFG_PATH.open('r') as f:
        return from_dict(data_class=Config, data=json.load(f))


settings = load_cfg()
save_cfg(settings)
