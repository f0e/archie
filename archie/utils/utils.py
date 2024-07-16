import time
from urllib.parse import urlparse

import yaml
from rich.style import Style

from archie import console


def log(*args, **kwargs):
    console.print(*args, **kwargs)


def module_log(module: str, module_style: str | Style | None, *args, **kwargs):
    console.print(f"[{module_style}]\\[{module}][/{module_style}] " + " ".join(map(str, args)), **kwargs)


def retryable(function, fail_function, max_retries=5, retry_delay_sec=5, on_exception=None):
    for i in range(max_retries):
        try:
            return function()
        except Exception as e:
            # TODO: print the error properly, HOW DO YOU DO THAT
            # error_console.print(repr(e))

            fail_function()
            time.sleep(retry_delay_sec)

            if on_exception:
                on_exception(e)

    return None


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
