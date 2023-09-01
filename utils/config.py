import json

from pathlib import Path

from dacite import from_dict

from pydantic import TypeAdapter
from pydantic.dataclasses import dataclass

CFG_PATH = Path('config.json')


@dataclass
class Config():
    min_subscribers: int = 0
    max_subscribers: int = 30000

    filter_verified: bool = False
    filter_livestreams: bool = True

    block_no_videos: bool = False
    max_videos: int = 300

    channel_update_gap_hours: int = 24
    video_update_gap_hours: int = 24 * 7


def load_cfg():
    if not CFG_PATH.exists() or CFG_PATH.stat().st_size == 0:
        with CFG_PATH.open('w') as f:
            # converts the config dataclass into json (bytes) and loads it
            data = json.loads(TypeAdapter(Config).dump_json(Config))
            json.dump(data, f, indent=2)

            return data

    with CFG_PATH.open('r') as f:
        return json.load(f)


def save_cfg(cfg):
    with CFG_PATH.open('w') as f:
        json.dump(cfg, f)


settings = from_dict(data_class=Config, data=load_cfg())
