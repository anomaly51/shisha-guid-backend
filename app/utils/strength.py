STRENGTH_RANGES = {
    "light": (0, 4.49),
    "medium": (4.5, 6.49),
    "strong": (6.5, 7.99),
    "heavy": (8, 10),
}


def clamp(value: float, minimum: float, maximum: float) -> float:
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
                return clamp(numeric, 0, 10)
        except (TypeError, ValueError):
            pass

    text = f"{getattr(tobacco, 'name', '') or ''} {getattr(tobacco, 'description', '') or ''}".lower()
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

    return clamp(score, 0, 10)


def matches_strength(value: float, strength: str | None) -> bool:
    if not strength or strength == "all":
        return True
    strength_range = STRENGTH_RANGES.get(strength)
    if not strength_range:
        return True
    return strength_range[0] <= value <= strength_range[1]
