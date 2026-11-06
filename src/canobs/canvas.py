"""Minimal Canvas REST client (stdlib only)."""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://chasacademy.instructure.com"


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
TOKEN_HELP = "Create a new one in Canvas (Account → Settings → New access token)"


class CanvasError(Exception):
    """A Canvas problem with a message meant for the user."""


def _load_token() -> str:
    token = os.environ.get("CANVAS_TOKEN")
    if token:
        return token
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "CANVAS_TOKEN" and value.strip():
                return value.strip().strip('"').strip("'")
    raise CanvasError(f"CANVAS_TOKEN is not set. Add it to {ENV_FILE} or export it.")


def _request(url: str):
    """Open a Canvas API URL, translating failures into CanvasError."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_load_token()}"})
    try:
        return urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise CanvasError(
                f"Canvas rejected the token (401): it has expired or been revoked. "
                f"{TOKEN_HELP} and update CANVAS_TOKEN."
            ) from None
        if e.code == 403:
            raise CanvasError(
                "Canvas refused access (403): your account can't see this course or resource."
            ) from None
        if e.code == 404:
            raise CanvasError(f"Not found on Canvas (404): {url.split('?')[0]}") from None
        if e.code == 429:
            raise CanvasError("Canvas is rate limiting requests (429). Wait a moment and retry.") from None
        raise CanvasError(f"Canvas returned HTTP {e.code} {e.reason}.") from None
    except urllib.error.URLError as e:
        raise CanvasError(f"Couldn't reach Canvas at {BASE_URL}: {e.reason}") from None
    except TimeoutError:
        raise CanvasError(f"Canvas at {BASE_URL} didn't respond within 30 seconds.") from None


def get_all(path: str, params: str = "") -> list:
    """GET a paginated Canvas endpoint, following Link rel=next."""
    url = f"{BASE_URL}/api/v1{path}?per_page=100{params}"
    results = []
    while url:
        with _request(url) as resp:
            results.extend(json.load(resp))
            m = re.search(r'<([^>]+)>;\s*rel="next"', resp.headers.get("Link", ""))
            url = m.group(1) if m else None
    return results


def modules(course_id: int) -> list:
    return get_all(f"/courses/{course_id}/modules")


def module_items(course_id: int, module_id: int) -> list:
    return get_all(f"/courses/{course_id}/modules/{module_id}/items")


def get_one(path: str) -> dict:
    with _request(f"{BASE_URL}/api/v1{path}") as resp:
        return json.load(resp)


def item_html(course_id: int, item: dict) -> str:
    """Return the HTML body of a Page or Assignment module item."""
    if item["type"] == "Page":
        return get_one(f"/courses/{course_id}/pages/{item['page_url']}").get("body") or ""
    if item["type"] == "Assignment":
        return get_one(f"/courses/{course_id}/assignments/{item['content_id']}").get("description") or ""
    raise ValueError(f"unsupported item type: {item['type']}")
