import sys
from os import getenv
from pathlib import Path


def get_datadir() -> Path:
    if sys.platform.startswith("win"):
        data_path = getenv("APPDATA", "~/AppData/Roaming")
    elif sys.platform.startswith("darwin"):
        data_path = "~/Library/Application Support"
    else:
        # linux
        data_path = getenv("XDG_DATA_HOME", "~/.local/share")

    if data_path is None:
        exit()

    return Path(data_path).expanduser()


ARCHIE_PATH = get_datadir() / "archie"
ARCHIE_PATH.mkdir(parents=True, exist_ok=True)
