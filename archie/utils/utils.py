from urllib.parse import urlparse

import yaml
from rich.style import Style

from archie import console


def log(*args, **kwargs):
    console.print(*args, **kwargs)


def module_log(module: str, module_style: str | Style | None, *args, **kwargs):
    console.print(f"[{module_style}]\\[{module}][/{module_style}] " + " ".join(map(str, args)), **kwargs)


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


class PrettyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)
