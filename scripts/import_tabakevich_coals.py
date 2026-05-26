#!/usr/bin/env python3
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


SOURCE_URLS = [
    "https://tabakevich.io/ugli-dlya-kalyana",
    "https://tabakevich.io/ugli-dlya-kalyana/kokosovye-ugli",
    "https://tabakevich.io/ugli-dlya-kalyana/orehoviy",
    "https://tabakevich.io/ugli-dlya-kalyana/drevesnye-ugli",
    "https://tabakevich.io/ugli-dlya-kalyana/bystrovozgorayushhiysya-ugol",
]

PLACEHOLDER_PATTERNS = (
    "/placeholder/",
    "placeholder",
    "image111.png",
)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def text_from_html(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<.*?>", " ", value)).split())


def absolute_url(url: str, base_url: str) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(url).strip())


def is_placeholder_image(url: str) -> bool:
    normalized = url.lower()
    return any(pattern in normalized for pattern in PLACEHOLDER_PATTERNS)


def product_blocks(page: str) -> list[str]:
    starts = [
        item.start()
        for item in re.finditer(r'<li[^>]+class="[^"]*\bitem\b', page, re.S | re.I)
    ]
    blocks = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(page)
        block = page[start:end]
        if "product-name" in block and "product-image" in block:
            blocks.append(block)
    return blocks


def parse_price(block: str) -> int:
    price_matches = re.findall(r'<span[^>]+class="price"[^>]*>(.*?)</span>', block, re.S)
    for raw_price in reversed(price_matches):
        price_text = text_from_html(raw_price).replace("\xa0", " ")
        match = re.search(r"(\d[\d\s]*)", price_text)
        if match:
            return int(match.group(1).replace(" ", ""))
    return 0


def parse_count(name: str) -> int | None:
    patterns = [
        r"(\d+)\s*(?:шт|штук|куб(?:\.|ик(?:а|ов)?)?)",
        r"(\d+)\s*pcs",
        r"(\d+)\s*pieces",
    ]
    for pattern in patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    if "поштучно" in name.lower():
        return 1
    return None


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


def parse_weight(name: str) -> str | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(кг|kg)\b", name, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1).replace(',', '.')} kg"
    match = re.search(r"(\d+)\s*(?:гр(?:\.|амм)?|грамм|g)\b", name, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)} g"
    return None


def parse_size(name: str) -> str | None:
    match = re.search(r"[сc]\s?(\d{2})\b", name, flags=re.IGNORECASE)
    if match:
        return f"C{match.group(1)}"
    match = re.search(r"(\d{2})\s*[xх*]\s*(\d{2})(?:\s*[xх*]\s*(\d{2}))?", name)
    if match:
        values = [match.group(index) for index in (1, 2, 3) if match.group(index)]
        return "x".join(values) + " mm"
    if "калауд" in name.lower() or "сегмент" in name.lower():
        return "kaloud segment"
    return None


def parse_category(name: str) -> str:
    normalized = name.lower()
    if "орех" in normalized:
        return "Ореховый уголь"
    if "древес" in normalized or "abo alabed" in normalized:
        return "Древесный уголь"
    if "быстров" in normalized or "carbopol" in normalized or "bagrad" in normalized:
        return "Быстроразжигаемыйся уголь"
    if "кокос" in normalized or "coco" in normalized:
        return "Кокосовый уголь"
    return "Уголь для кальяна"


def parse_products(page: str, source_url: str) -> list[dict]:
    products = []
    for block in product_blocks(page):
        name_match = re.search(
            r'<p[^>]+class="product-name"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            block,
            re.S | re.I,
        )
        image_match = re.search(
            r'<a[^>]+class="product-image"[^>]*>.*?<img[^>]+src="([^"]+)"',
            block,
            re.S | re.I,
        )
        if not name_match:
            continue

        product_url = absolute_url(name_match.group(1), source_url)
        name = text_from_html(name_match.group(2))
        if "угол" not in name.lower() and "coal" not in name.lower():
            continue

        image_url = absolute_url(image_match.group(1), source_url) if image_match else ""
        photo_urls = [image_url] if image_url and not is_placeholder_image(image_url) else []
        count = parse_count(name)
        weight = parse_weight(name)
        size = parse_size(name)
        coal_type = parse_category(name)

        details = [coal_type]
        if weight:
            details.append(f"Фасовка: {weight}.")
        if count:
            details.append(f"Количество: {count} шт.")
        if size:
            details.append(f"Формат: {size}.")
        details.append(f"Источник карточки: {product_url}")
        details.append("Данные добавлены из публичного каталога Tabakevich.")

        products.append(
            {
                "name": clean_coal_name(name),
                "description": " ".join(details),
                "photo_urls": photo_urls,
                "price": parse_price(block),
                "price_currency": "UAH",
                "coals_per_package": count,
            }
        )
    return products


def next_page_url(page: str, current_url: str) -> str | None:
    match = re.search(r'<a[^>]+rel="next"[^>]+href="([^"]+)"', page, re.S | re.I)
    if not match:
        return None
    return absolute_url(match.group(1), current_url)


def collect_products(delay: float = 0.2) -> list[dict]:
    products_by_name = {}
    seen_pages = set()
    queue = list(SOURCE_URLS)

    while queue:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        try:
            page = fetch_text(url)
        except urllib.error.URLError as error:
            print(f"skip {url}: {error}", file=sys.stderr)
            continue

        for product in parse_products(page, url):
            products_by_name.setdefault(product["name"], product)

        next_url = next_page_url(page, url)
        if next_url and next_url not in seen_pages:
            queue.append(next_url)
        if delay:
            time.sleep(delay)

    return sorted(products_by_name.values(), key=lambda item: item["name"].lower())


def api_request(method: str, url: str, token: str | None = None, body: dict | None = None):
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
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
    parser = argparse.ArgumentParser(description="Import Tabakevich coal catalog.")
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get(
            "SHISHA_GUID_API_URL",
            "https://shisha-guid-api.api-api-api.com/api/v1",
        ),
    )
    parser.add_argument("--token", default=os.environ.get("SHISHA_GUID_TOKEN"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    products = collect_products()
    if args.limit > 0:
        products = products[:args.limit]
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
