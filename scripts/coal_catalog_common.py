import json
import re
import urllib.error
import urllib.request


def clean_coal_name(name: str) -> str:
    cleaned = name
    cleaned = re.sub(r"\(?\s*\d+[\d\s]*(?:грн|₴|uah)\s*\)?", " ", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\(?\s*\d+\s*(?:шт\.?|штук|куб(?:\.|ик(?:а|ов)?)?|pcs|pieces)\s*\)?",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\(\s*\)", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"([,.;:])\s*([,.;:])+", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -.,")
    return cleaned or name


def api_request(method: str, url: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else None
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", "ignore")
        raise RuntimeError(f"{method} {url} failed: {error.code} {details}") from error
