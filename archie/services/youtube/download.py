from rich.progress import Progress, TaskID

from ..base_download import rich_progress


class YTProgressData:
    filename: str
    tmpfilename: str
    downloaded_bytes: int
    total_bytes: int | None
    total_bytes_estimate: int | None
    elapsed: int
    eta: int
    speed: float
    fragment_index: int | None
    fragment_count: int | None

    def __init__(self, data):
        self.filename = data.get("filename")
        self.tmpfilename = data.get("tmpfilename")
        self.downloaded_bytes = data.get("downloaded_bytes")
        self.total_bytes = data.get("total_bytes")
        self.total_bytes_estimate = data.get("total_bytes_estimate")
        self.elapsed = data.get("elapsed")
        self.eta = data.get("eta")
        self.speed = data.get("speed")
        self.fragment_index = data.get("fragment_index")
        self.fragment_count = data.get("fragment_count")


class ProgressBar:
    task_id: TaskID

    def __init__(self, channel, video):
        self.task_id = rich_progress.add_task(
            "download", service="youtube", author=channel["channel"], title=video["title"], start=False, total=0
        )

    def __del__(self):
        rich_progress.remove_task(self.task_id)

    def update(self, progress_data: YTProgressData):
        rich_progress.start_task(self.task_id)
        rich_progress.update(task_id=self.task_id, completed=progress_data.downloaded_bytes, total=progress_data.total_bytes)


progresses: dict[str, ProgressBar] = dict()


def progress_hooks(data):
    match data["status"]:
        case "downloading":
            video_id = data["info_dict"]["id"]

            assert video_id in progresses
            progress = progresses[video_id]

            progress_data = YTProgressData(data)

            rich_progress.start_task(progress.task_id)
            rich_progress.update(progress.task_id)

            if video_id not in progresses:
                progresses[video_id] = Progress(video_id)

            progresses[video_id].update(progress_data)


def start_progress(channel, video):
    progresses[video["id"]] = ProgressBar(channel, video)


def finish_progress(video):
    if video["id"] in progresses:
        del progresses[video["id"]]
