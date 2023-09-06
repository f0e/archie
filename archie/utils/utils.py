import threading
from urllib.parse import urlparse

import click
import requests
import yaml

print_lock = threading.RLock()  # rlock - same thread can acquire multiple times, other threads have to wait


def safe_log(module: str, module_colour: str, *args, **kwargs):
    with print_lock:
        click.echo(click.style(f"[{module}] ", fg=module_colour) + " ".join(map(str, args)), **kwargs)


def validate_url(x):
    try:
        result = urlparse(x)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def find(iterable, pred):
    for element in iterable:
        if pred(element):
            return element
    return None


def download_image(url):
    response = requests.get(url)

    if response.status_code == 200:
        return response.content
    else:
        click.echo(f"Failed to download image from URL: {url}")
        return None


class PrettyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)
