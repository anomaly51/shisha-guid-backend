#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys

from coal_catalog_common import api_request, clean_coal_name


def parse_count(text: str) -> int | None:
    patterns = [
        r"(\d+)\s*(?:шт\.?|штук|куб(?:\.|ик(?:а|ов)?)?|pcs|pieces)\b",
        r"Количество:\s*(\d+)\s*шт",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return int(match.group(1))
    return None


def parse_weight_kg(text: str) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:кг|kg)\b", text, flags=re.I)
    if match:
        return float(match.group(1).replace(",", "."))
    match = re.search(r"(\d+)\s*(?:гр(?:\.|амм)?|грамм|g)\b", text, flags=re.I)
    if match:
        return int(match.group(1)) / 1000
    return None


def infer_count(name: str, description: str | None) -> int | None:
    text = f"{name} {description or ''}".lower()
    explicit = parse_count(text)
    if explicit:
        return explicit

    weight = parse_weight_kg(text)
    if weight is None:
        return None
    if weight > 2:
        return None

    if "под калауд" in text or "сегмент" in text or "quad" in text:
        return round(weight * 112)
    if re.search(r"(?:с|c|p|р)\s?22\b|22\s*мм|22mm", text, flags=re.I):
        return round(weight * 96)
    if re.search(r"(?:с|c|p|р)\s?26\b|26\s*(?:мм|mm|р|p)\b|\b26\b", text, flags=re.I):
        return round(weight * 64)
    if re.search(r"(?:с|c|p|р)\s?25\b|25\s*(?:х|x|\*)\s*25|25\s*мм|25mm", text, flags=re.I):
        return round(weight * 72)

    if weight <= 0.3:
        return round(weight * 72)
    if 0.45 <= weight <= 0.6:
        return round(weight * 72)
    if 0.9 <= weight <= 1.1:
        return 72
    return None


def normalize_item(item: dict) -> dict | None:
    next_item = {
        "name": clean_coal_name(item.get("name") or ""),
        "description": item.get("description"),
        "photo_urls": item.get("photo_urls") or [],
        "price": item.get("price") or 0,
        "price_currency": item.get("price_currency") or "UAH",
        "coals_per_package": item.get("coals_per_package"),
    }
    if not next_item["coals_per_package"]:
        next_item["coals_per_package"] = infer_count(
            item.get("name") or "",
            item.get("description"),
        )

    changed = any(next_item.get(key) != item.get(key) for key in next_item)
    return next_item if changed else None


def get_all_coals(api_base_url: str) -> list[dict]:
    coals_url = f"{api_base_url.rstrip('/')}/shisha/coals"
    response = api_request("GET", f"{coals_url}?limit=100&offset=0") or []
    if isinstance(response, dict) and "items" in response:
        items = list(response["items"])
        offset = len(items)
        while response.get("has_more"):
            response = api_request("GET", f"{coals_url}?limit=100&offset={offset}") or {}
            page_items = response.get("items") or []
            items.extend(page_items)
            offset += len(page_items)
        return items
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize coal names and pack counts.")
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get(
            "SHISHA_GUID_API_URL",
            "https://shisha-guid-api.api-api-api.com/api/v1",
        ),
    )
    parser.add_argument("--token", default=os.environ.get("SHISHA_GUID_TOKEN"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.token:
        print("Missing --token or SHISHA_GUID_TOKEN", file=sys.stderr)
        return 2

    coals_url = f"{args.api_base_url.rstrip('/')}/shisha/coals"
    coals = get_all_coals(args.api_base_url)
    updates = []
    for item in coals:
        payload = normalize_item(item)
        if payload:
            updates.append((item, payload))

    print(f"Loaded {len(coals)} coals, updates {len(updates)}")
    if args.dry_run:
        preview = [
            {
                "id": item.get("id"),
                "from": item.get("name"),
                "to": payload["name"],
                "coals_per_package": payload.get("coals_per_package"),
            }
            for item, payload in updates
        ]
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0

    for item, payload in updates:
        api_request("PATCH", f"{coals_url}/{item['id']}", args.token, payload)

    print(f"Updated {len(updates)} coals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
