import shutil
from pathlib import Path

from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Column

from archie import console
from archie.config import TEMP_DL_PATH, ArchiveConfig
from archie.utils import utils


def log(*args, **kwargs):
    utils.log(*args, **kwargs, style="dim")


class MyProgress(Progress):
    def get_renderables(self):
        yield Panel(self.make_tasks_table(self.tasks), title="downloads", title_align="left", border_style="dim")


rich_progress = MyProgress(
    TaskProgressColumn(justify="right", table_column=Column(width=4)),
    BarColumn(bar_width=20, table_column=Column(width=20)),
    TextColumn(
        "{task.fields[service]}: [bold blue]{task.fields[author]} - {task.fields[title]}",
        table_column=Column(ratio=1, no_wrap=True),
    ),
    TimeRemainingColumn(table_column=Column(width=10)),
    DownloadColumn(table_column=Column(width=15)),
    console=console,
    expand=True,
)

# TODO: move more of the code here from youtube, give generic methods for stuff

# remove temp downloads (for safety, resuming causes issues sometimes)
if TEMP_DL_PATH.exists():
    shutil.rmtree(TEMP_DL_PATH)

TEMP_DL_PATH.mkdir(parents=True, exist_ok=True)


def copy_download(
    service_name: str, path: Path, relative_path: Path, archive: ArchiveConfig
):  # TODO: just pass copy path rather than config?
    if not path.exists():
        raise Exception("copying file does not exist")

    # user wants this channel's videos downloaded to another path as well. hardlink the video rather than redownloading
    copy_path = Path(archive.downloads.download_path) / service_name / relative_path

    if not copy_path.exists():
        log(f"copying from {path} to {copy_path}")

        copy_path.parent.mkdir(parents=True, exist_ok=True)
        copy_path.hardlink_to(path)

        log(f"hardlinked video from {path} to {copy_path}")
