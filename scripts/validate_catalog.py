#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request


DEFAULT_API_BASE_URL = "https://shisha-guid-api.api-api-api.com/api/v1"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def api_get(url: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_page(api_base_url: str, path: str) -> list[dict]:
    url = f"{api_base_url.rstrip('/')}{path}"
    response = api_get(url)
    if isinstance(response, list):
        return response
    if not isinstance(response, dict) or "items" not in response:
        raise RuntimeError(f"Unexpected response shape for {path}")

    items = list(response["items"])
    offset = len(items)
    while response.get("has_more"):
        separator = "&" if "?" in path else "?"
        response = api_get(f"{url}{separator}offset={offset}")
        page_items = response.get("items") or []
        items.extend(page_items)
        offset += len(page_items)
    return items


def load_catalog(api_base_url: str) -> dict[str, list[dict]]:
    return {
        "tobaccos": get_page(api_base_url, "/shisha/tobaccos?limit=100"),
        "coals": get_page(api_base_url, "/shisha/coals?limit=100"),
        "bowls": get_page(api_base_url, "/shisha/bowls"),
        "kalouds": get_page(api_base_url, "/shisha/kalouds"),
    }


def load_file(path: str) -> dict[str, list[dict]]:
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    if isinstance(data, list):
        return {"items": data}
    return data


def has_price_in_name(name: str) -> bool:
    return bool(re.search(r"(?:^|[\s(])\d+[\d\s]*(?:грн|₴|uah)\b", name, re.I))


def has_pack_count_in_name(name: str) -> bool:
    return bool(
        re.search(
            r"\b\d+\s*(?:шт\.?|штук|куб(?:\.|ик(?:а|ов)?)?|pcs|pieces)\b",
            name,
            re.I,
        )
    )


def validate_catalog(catalog: dict[str, list[dict]]) -> list[str]:
    warnings: list[str] = []
    seen_names: dict[str, dict[str, str]] = {}

    for section, items in catalog.items():
        section_seen = seen_names.setdefault(section, {})
        for item in items:
            name = item.get("name") or ""
            normalized_name = name.casefold().strip()
            item_id = item.get("id") or "unknown-id"

            if not name.strip():
                warnings.append(f"{section}:{item_id}: empty name")
            if normalized_name and normalized_name in section_seen:
                warnings.append(
                    f"{section}:{item_id}: duplicate name with {section_seen[normalized_name]}: {name}"
                )
            if normalized_name:
                section_seen[normalized_name] = f"{section}:{item_id}"

            if has_price_in_name(name):
                warnings.append(f"{section}:{item_id}: price in name: {name}")

            if section == "coals":
                if has_pack_count_in_name(name):
                    warnings.append(f"{section}:{item_id}: pack count in name: {name}")
                if item.get("coals_per_package") in (None, 0):
                    warnings.append(f"{section}:{item_id}: missing coals_per_package: {name}")

            if section in {"tobaccos", "coals", "bowls", "kalouds"}:
                price = item.get("price")
                if not isinstance(price, int) or price < 0:
                    warnings.append(f"{section}:{item_id}: invalid price {price!r}: {name}")
                photos = item.get("photo_urls") or []
                if not isinstance(photos, list):
                    warnings.append(f"{section}:{item_id}: photo_urls is not list: {name}")

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate public catalog data quality.")
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("SHISHA_GUID_API_URL", DEFAULT_API_BASE_URL),
    )
    parser.add_argument("--file", help="Validate a local JSON export instead of API.")
    args = parser.parse_args()

    try:
        catalog = load_file(args.file) if args.file else load_catalog(args.api_base_url)
    except (OSError, urllib.error.URLError, RuntimeError) as error:
        print(f"Failed to load catalog: {error}", file=sys.stderr)
        return 2

    warnings = validate_catalog(catalog)
    print(f"Checked {sum(len(items) for items in catalog.values())} items")
    if not warnings:
        print("No catalog warnings")
        return 0

    for warning in warnings:
        print(f"- {warning}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
