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
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "https://hakyemezi.github.io/turkeyFundLens/"
ENDPOINT = "https://api.indexnow.org/indexnow"


def find_key() -> str:
    """The key is the name of the 32-character hex .txt file beside the other ownership files."""
    for file in (HERE / "verification").glob("*.txt"):
        if re.fullmatch(r"[0-9a-f]{32}", file.stem) and file.read_text().strip() == file.stem:
            return file.stem
    raise SystemExit("No IndexNow key file in site/verification/")


def main(base_url: str = DEFAULT_BASE_URL) -> None:
    key = find_key()
    try:
        with urllib.request.urlopen(base_url + "sitemap.xml", timeout=60) as response:
            urls = re.findall(r"<loc>(.*?)</loc>", response.read().decode("utf-8"))
        body = json.dumps(
            {
                "host": urlparse(base_url).netloc,
                "key": key,
                "keyLocation": f"{base_url}{key}.txt",
                "urlList": urls[:10000],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            ENDPOINT, data=body, headers={"Content-Type": "application/json; charset=utf-8"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            print(f"IndexNow: sent {len(urls)} addresses, answer {response.status}")
    except Exception as error:  # noqa: BLE001 - reported, never fatal
        print(f"IndexNow: not sent ({error})")


if __name__ == "__main__":
    main(*sys.argv[1:2])
