#!/usr/bin/env python3
import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


SOURCE_URLS = [
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-ignis",
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-tom-cococha",
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-phoenix",
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-panda",
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-garden",
    "https://hookahmarket.vip/katalog/ugli/kokosovyj-ugol-dlya-kalyana-cocoloco",
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-eskobar",
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-lavart",
    "https://hookahmarket.vip/katalog/ugli/kokosovyj-ugol-dlya-kalyana-noname",
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-caliber",
    "https://hookahmarket.vip/katalog/ugli/orehovyiy-ugol-dlya-kalyana-mind",
    "https://hookahmarket.vip/katalog/ugli/orehovyiy-ugol-dlya-kalyana-gresco",
    "https://hookahmarket.vip/katalog/ugli/kokosovyiy-ugol-dlya-kalyana-lagom",
]


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "KHTML, like Gecko) Chrome/120 Safari/537.36"
            ),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def text_from_html(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<.*?>", " ", value)).split())


def product_blocks(page: str) -> list[str]:
    marker = '<div class="product-block product-thumb transition">'
    starts = [match.start() for match in re.finditer(re.escape(marker), page)]
    blocks = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else min(len(page), start + 50000)
        blocks.append(page[start:end])
    return blocks


def parse_count(name: str) -> int | None:
    match = re.search(r"(\d+)\s*шт", name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_size(name: str) -> str | None:
    match = re.search(r"(?:р|p)\s?(\d{2})", name, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)} mm cube"
    if "сегмент" in name.lower():
        return "kaloud segment"
    return None


def parse_weight(name: str) -> str | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*кг", name, flags=re.IGNORECASE)
    return f"{match.group(1).replace(',', '.')} kg" if match else None


def parse_products(page: str, source_url: str) -> list[dict]:
    products = []
    for block in product_blocks(page):
        name_match = re.search(r'<span class="sales-names-b">(.*?)</span>', block, re.S)
        image_match = re.search(r'<img[^>]+src="([^"]+)"', block)
        price_match = re.search(r'<div class="price">(.*?)</div>', block, re.S)
        href_match = re.search(r'<a href="([^"]+)" class="sales-name-text">', block)
        if not name_match:
            continue

        name = text_from_html(name_match.group(1))
        if "уголь" not in name.lower():
            continue

        price_text = text_from_html(price_match.group(1)) if price_match else ""
        price_value = re.search(r"(\d+)\s*₴", price_text)
        image_url = html.unescape(image_match.group(1)).strip() if image_match else ""
        product_url = html.unescape(href_match.group(1)).strip() if href_match else source_url
        count = parse_count(name)
        size = parse_size(name)
        weight = parse_weight(name)

        details = []
        if weight:
            details.append(f"Фасовка: {weight}")
        if count:
            details.append(f"Количество: {count} шт.")
        if size:
            details.append(f"Формат: {size}")
        details.append(f"Источник карточки: {product_url}")
        details.append("Данные добавлены из публичного каталога HookahMarket.")

        products.append(
            {
                "name": name,
                "description": " ".join(details),
                "photo_urls": [image_url] if image_url else [],
                "price": int(price_value.group(1)) if price_value else 0,
                "price_currency": "UAH",
                "coals_per_package": count,
            }
        )
    return products


def collect_products() -> list[dict]:
    products_by_name = {}
    for source_url in SOURCE_URLS:
        try:
            page = fetch_text(source_url)
        except urllib.error.URLError as error:
            print(f"skip {source_url}: {error}", file=sys.stderr)
            continue
        for product in parse_products(page, source_url):
            products_by_name.setdefault(product["name"], product)
    return sorted(products_by_name.values(), key=lambda item: item["name"].lower())


def api_request(method: str, url: str, token: str | None = None, body: dict | None = None):
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", "ignore")
        raise RuntimeError(f"{method} {url} failed: HTTP {error.code} {details}") from error


def import_products(api_base_url: str, token: str, products: list[dict]) -> tuple[int, int]:
    coals_url = f"{api_base_url.rstrip('/')}/shisha/coals"
    existing = api_request("GET", coals_url) or []
    existing_by_name = {item.get("name"): item for item in existing if item.get("name")}
    created = 0
    updated = 0

    for product in products:
        current = existing_by_name.get(product["name"])
        if current:
            api_request("PATCH", f"{coals_url}/{current['id']}", token, product)
            updated += 1
        else:
            api_request("POST", coals_url, token, product)
            created += 1

    return created, updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Import HookahMarket coal catalog.")
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

    products = collect_products()
    print(f"Collected {len(products)} coals")

    if args.dry_run:
        print(json.dumps(products, ensure_ascii=False, indent=2))
        return 0

    if not args.token:
        print("Missing --token or SHISHA_GUID_TOKEN", file=sys.stderr)
        return 2

    created, updated = import_products(args.api_base_url, args.token, products)
    print(f"Created {created}, updated {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
