import logging
import sys
from os import getenv
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

console = Console(highlight=False)
error_console = Console(stderr=True, highlight=False)

FORMAT = "%(message)s"
logging.basicConfig(level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
log = logging.getLogger("rich")


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
