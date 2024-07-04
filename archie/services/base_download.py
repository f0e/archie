import shutil

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from archie import console
from archie.config import TEMP_DL_PATH

rich_progress = Progress(
    TaskProgressColumn(justify="right"),
    BarColumn(bar_width=30),
    TextColumn("[bold blue]{task.fields[video].channel.name} - {task.fields[video].title}"),
    TimeRemainingColumn(),
    DownloadColumn(),
    console=console,
)

# TODO: move more of the code here from youtube, give generic methods for stuff

# remove temp downloads (for safety, resuming causes issues sometimes)
if TEMP_DL_PATH.exists():
    shutil.rmtree(TEMP_DL_PATH)

TEMP_DL_PATH.mkdir(parents=True, exist_ok=True)
