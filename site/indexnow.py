"""
Tell the IndexNow search engines (Bing, Yandex and others) what was published.

Google does not take part; it gets the sitemap through Search Console. For the
rest, waiting to be crawled can take weeks on a new site with no links to it,
and every page here changes every working day. This reads the sitemap the
build just published and sends its addresses in one request.

Run after the site is deployed:

    python site/indexnow.py

It never fails the workflow: a search engine being unreachable is no reason
to mark a good build red.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "https://hakyemezi.github.io/turkeyFundLens/"
ENDPOINT = "https://api.indexnow.org/indexnow"

# The first run was refused with 403: it asked seconds after the deploy, before
# the key file it names could be fetched. So the request waits for the key to be
# reachable, and is repeated a few times if it is still refused.
ATTEMPTS = 5
PAUSE_SECONDS = 30


def find_key() -> str:
    """The key is the name of the 32-character hex .txt file beside the other ownership files."""
    for file in (HERE / "verification").glob("*.txt"):
        if re.fullmatch(r"[0-9a-f]{32}", file.stem) and file.read_text().strip() == file.stem:
            return file.stem
    raise SystemExit("No IndexNow key file in site/verification/")


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001
        return False


def main(base_url: str = DEFAULT_BASE_URL) -> None:
    key = find_key()
    key_location = f"{base_url}{key}.txt"
    try:
        with urllib.request.urlopen(base_url + "sitemap.xml", timeout=60) as response:
            urls = re.findall(r"<loc>(.*?)</loc>", response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001 - reported, never fatal
        print(f"IndexNow: not sent, the sitemap could not be read ({error})")
        return

    body = json.dumps(
        {
            "host": urlparse(base_url).netloc,
            "key": key,
            "keyLocation": key_location,
            "urlList": urls[:10000],
        }
    ).encode("utf-8")

    for attempt in range(1, ATTEMPTS + 1):
        if reachable(key_location):
            request = urllib.request.Request(
                ENDPOINT, data=body, headers={"Content-Type": "application/json; charset=utf-8"}
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    print(f"IndexNow: sent {len(urls)} addresses, answer {response.status}")
                    return
            except urllib.error.HTTPError as error:
                reason = f"answer {error.code}"
            except Exception as error:  # noqa: BLE001 - reported, never fatal
                reason = str(error)
        else:
            reason = "the key file is not reachable yet"
        print(f"IndexNow: attempt {attempt}/{ATTEMPTS} failed ({reason})")
        if attempt < ATTEMPTS:
            time.sleep(PAUSE_SECONDS)
    print("IndexNow: not sent")


if __name__ == "__main__":
    main(*sys.argv[1:2])
