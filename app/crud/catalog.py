from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.shisha import Coal, Tobacco

TRANSLIT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)

SEARCH_SYNONYMS = {
    "blueberry": ("голубика", "черника", "блюберри"),
    "grape": ("виноград",),
    "lemon": ("лимон",),
    "lime": ("лайм",),
    "mango": ("манго",),
    "mint": ("мята", "mint"),
    "peach": ("персик",),
    "strawberry": ("клубника",),
    "vanilla": ("ваниль",),
}

STRENGTH_RANGES = {
    "light": (0, 4.49),
    "medium": (4.5, 6.49),
    "strong": (6.5, 7.99),
    "heavy": (8, 10),
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def get_tobacco_strength(tobacco) -> float:
    explicit_value = next(
        (
            value
            for value in (
                getattr(tobacco, "strength", None),
                getattr(tobacco, "heaviness", None),
                getattr(tobacco, "nicotine_strength", None),
                getattr(tobacco, "nicotine", None),
            )
            if value is not None
        ),
        None,
    )
    if explicit_value is not None:
        try:
            numeric = float(explicit_value)
            if numeric >= 0:
                return _clamp(numeric, 0, 10)
        except (TypeError, ValueError):
            pass

    text = (
        f"{getattr(tobacco, 'name', '') or ''} "
        f"{getattr(tobacco, 'description', '') or ''}"
    ).lower()
    score = 5

    if "darkside" in text:
        score += 3
    if "blackburn" in text or "strong" in text or "креп" in text:
        score += 2
    if "musthave" in text or "sebero" in text:
        score += 1
    if "duft" in text or "mango" in text or "слив" in text or "мягк" in text:
        score -= 1
    if "element" in text or "banana" in text or "milk" in text or "легк" in text:
        score -= 2

    return _clamp(score, 0, 10)


def matches_strength(value: float, strength: str | None) -> bool:
    if not strength or strength == "all":
        return True
    strength_range = STRENGTH_RANGES.get(strength)
    if not strength_range:
        return True
    return strength_range[0] <= value <= strength_range[1]


def _normalize_search_text(value: str | None) -> str:
    normalized = (value or "").casefold().replace("ё", "е")
    normalized = normalized.translate(TRANSLIT)
    return " ".join(normalized.split())


def _search_terms(search: str | None) -> list[str]:
    normalized = _normalize_search_text(search)
    if not normalized:
        return []
    terms = {normalized, *normalized.split()}
    for key, values in SEARCH_SYNONYMS.items():
        synonym_values = {_normalize_search_text(value) for value in (key, *values)}
        if terms & synonym_values:
            terms.update(synonym_values)
    return [term for term in terms if term]


def _matches_search(item, search: str | None) -> bool:
    terms = _search_terms(search)
    if not terms:
        return True
    haystack = _normalize_search_text(
        f"{getattr(item, 'name', '') or ''} {getattr(item, 'description', '') or ''}"
    )
    return any(term in haystack for term in terms)


async def get_filtered_tobaccos(
    db: AsyncSession,
    min_price: int | None = None,
    max_price: int | None = None,
    strength: str | None = None,
    search: str | None = None,
):
    query = select(Tobacco)
    if min_price is not None:
        query = query.where(Tobacco.price >= min_price)
    if max_price is not None:
        query = query.where(Tobacco.price <= max_price)
    result = await db.execute(query.order_by(func.lower(Tobacco.name)))
    tobaccos = result.scalars().all()
    return [
        tobacco
        for tobacco in tobaccos
        if matches_strength(get_tobacco_strength(tobacco), strength)
        and _matches_search(tobacco, search)
    ]


async def get_tobaccos_page(
    db: AsyncSession,
    min_price: int | None = None,
    max_price: int | None = None,
    strength: str | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    limit = max(1, min(limit or 24, 100))
    offset = max(0, offset)
    tobaccos = await get_filtered_tobaccos(
        db,
        min_price=min_price,
        max_price=max_price,
        strength=strength,
        search=search,
    )
    total = len(tobaccos)
    items = tobaccos[offset : offset + limit]
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


async def get_coals_page(
    db: AsyncSession,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    limit = max(1, min(limit or 24, 100))
    offset = max(0, offset)
    query = select(Coal)

    result = await db.execute(query.order_by(func.lower(Coal.name)))
    coals = [coal for coal in result.scalars().all() if _matches_search(coal, search)]
    total = len(coals)
    items = coals[offset : offset + limit]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }
