import json
import time
import yt_dlp

from utils.utils import download_image
from database.database import db, Channel


def debug_write(yt, data):
    with open("out.json", "w") as out_file:
        out_file.write(json.dumps(yt.sanitize_info(data)))


def get_channel(channel):
    # fetches channel info and video list. videos only contain basic information
    ydl_opts = {
        'extract_flat': True,
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as yt:
        URL = f'https://www.youtube.com/{channel}'
        info = yt.extract_info(URL, download=False)

        # todo: do all channels have at least one avatar? this will fail if not
        avatar_data = download_image(info['thumbnails'][0]['url'])

        Channel.create_or_update(
            id=info['id'],
            name=info['channel'],
            avatar=avatar_data,
            description=info['description']
        )
