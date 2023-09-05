import requests


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
        print(f"Failed to download image from URL: {url}")
        return None
