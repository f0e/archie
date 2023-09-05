import json

from pathlib import Path
import os

from pydantic import BaseModel, Field

CFG_PATH = Path('config.json')


class Config(BaseModel):
    archie_path: str = Field(default=os.path.join(Path.home(), "archie"))

    min_subscribers: int = Field(default=0)
    max_subscribers: int = Field(default=30000)

    filter_verified: bool = Field(default=False)
    filter_livestreams: bool = Field(default=True)

    block_no_videos: bool = Field(default=False)
    max_videos: int = Field(default=300)

    channel_update_gap_hours: int = Field(default=24)
    video_update_gap_hours: int = Field(default=24 * 7)

    def to_json(self):
        return json.loads(self.model_dump_json())

    # add any missing keys from a config
    def patch_keys(self, cfg_file: Path):
        data = self.to_json()

        with cfg_file.open('r+') as f:
            cfg_data = json.load(f)

            for key in data.keys():
                value = data[key]

                if key not in cfg_data:
                    print(f'missing {key}')

                    cfg_data[key] = value
                    save_cfg(cfg_data)


def save_cfg(data):
    with CFG_PATH.open('w') as f:
        json.dump(data, f, indent=2)


def load_cfg():
    if not CFG_PATH.exists() or CFG_PATH.stat().st_size == 0:
        save_cfg(Config().to_json())

    with CFG_PATH.open('r') as f:
        return Config().model_validate_json(f.read())


settings = load_cfg()
settings.patch_keys(CFG_PATH)
