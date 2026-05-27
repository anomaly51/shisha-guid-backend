import json
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, get_optional_current_user
from app.crud import shisha as crud
from app.models.shisha import Bowl, BowlSetupType, Coal, CoalPlacement, Kaloud, Tobacco
from app.models.user import User
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentSetupDraft,
    AgentTranscribeResponse,
)
from app.schemas.shisha import BowlSetupCreate, BowlSetupTobaccoCreate

router = APIRouter()
logger = logging.getLogger(__name__)

_rate_limits: dict[str, deque[datetime]] = defaultdict(deque)

REQUIRED_FIELDS = {
    "name": "название забивки",
    "bowl_id": "чаша",
    "kaloud_id": "калауд",
    "coal_id": "уголь",
    "coal_placement_id": "раскладка углей",
    "bowl_setup_type_id": "тип забивки",
}

AGENT_SYSTEM_PROMPT = """
Ты чат-агент ShishaGuid для добавления забивки.
Отвечай пользователю на русском кратко и по делу.
Твоя задача: собрать черновик забивки из текста пользователя, сверить его с каталогом,
обновить уже выбранные поля формы и попросить проверить черновик. Самостоятельно
не публикуй забивку.

Правила:
- Если последнее сообщение пользователя является приветствием, small talk,
  вопросом о возможностях чата или коротким непонятным вводом, ответь
  разговорно и направь пользователя к описанию забивки. Не перечисляй
  недостающие поля и не делай вид, что черновик обновлен.
- Перечисляй недостающие поля только когда пользователь уже описывает забивку,
  явно спрашивает что осталось выбрать или просит продолжить сборку.
- Используй только id из переданного каталога. Не выдумывай id.
- Если пользователь назвал сущность, выбери самый близкий элемент каталога.
- Если в current_draft уже есть выбранная чаша, калауд, уголь, расположение углей
  или тип забивки и пользователь не просил их поменять, сохрани эти значения.
- Уголь означает конкретный уголь из каталога coals. Расположение углей означает
  схему/количество углей из coal_placements. Не путай эти поля.
- Если нужного элемента нет в каталоге, спроси уточнение и не создавай забивку.
- Если пользователь просит тебя выбрать всё самому, заполнить тестово, подобрать
  любые подходящие значения, сделать демо-черновик или рандомную/случайную
  забивку, либо пишет в разговорной форме "забей сам", "собери сам",
  "сделай сам", "любой", "на твой вкус", выбери конкретные позиции из каталога
  для всех обязательных полей и верни их в draft. Не ограничивайся текстовым
  описанием.
- Если пользователь подтверждает предложенный тобой набор, верни этот набор в
  draft как структурные поля. После подтверждения не показывай каталог заново.
- Любой конкретный табак, чаша, калауд, уголь, раскладка или тип забивки,
  которые ты называешь в reply как выбранные/предложенные для текущего черновика,
  должны быть также заполнены в draft с id и name из каталога.
- Нельзя писать "проверь карточку", "черновик готов" или похожий текст, если
  draft не содержит выбранные значения, которые должна показать карточка.
- Если draft заполнен полностью, action должен быть "confirm", а reply должен
  попросить проверить карточку черновика и нажать кнопку публикации в интерфейсе.
- В ответе спрашивай только те поля, которых реально не хватает в черновике.
  Не предлагай заново чашу, калауд, уголь, раскладку или тип, если они уже выбраны.
  Не перечисляй весь каталог и не давай варианты "на всякий случай".
- Если проценты табаков не указаны, распредели табаки поровну.
- Не возвращай action=create_setup из обычного чата. Публикация выполняется только
  отдельной кнопкой интерфейса, не текстовым подтверждением пользователя.
- Верни только JSON без markdown.

JSON schema:
{
  "reply": "сообщение пользователю",
  "action": "collect" | "confirm" | "create_setup",
  "draft": {
    "name": string | null,
    "description": string | null,
    "bowl_id": string | null,
    "bowl_name": string | null,
    "kaloud_id": string | null,
    "kaloud_name": string | null,
    "coal_id": string | null,
    "coal_name": string | null,
    "coal_placement_id": string | null,
    "coal_placement_name": string | null,
    "bowl_setup_type_id": string | null,
    "bowl_setup_type_name": string | null,
    "tobaccos": [
      {"tobacco_id": string | null, "tobacco_name": string | null, "percentage": number | null}
    ]
  }
}
""".strip()


async def _catalog_items(db: AsyncSession, model) -> list[dict[str, Any]]:
    query = select(model)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    result = await db.execute(
        query
        .order_by(func.lower(model.name), model.created_at)
        .limit(settings.AGENT_CATALOG_LIMIT)
    )
    return [
        {
            "id": str(item.id),
            "name": item.name,
            "description": item.description,
        }
        for item in result.scalars().all()
    ]


async def _load_catalog(db: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    return {
        "bowls": await _catalog_items(db, Bowl),
        "kalouds": await _catalog_items(db, Kaloud),
        "coals": await _catalog_items(db, Coal),
        "coal_placements": await _catalog_items(db, CoalPlacement),
        "bowl_setup_types": await _catalog_items(db, BowlSetupType),
        "tobaccos": await _catalog_items(db, Tobacco),
    }


def _parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Agent returned non-object JSON")
    return parsed


def _catalog_ids(catalog: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    return {key: {item["id"] for item in items} for key, items in catalog.items()}


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold().replace("ё", "е")).strip()


def _catalog_item_by_name(
    catalog: dict[str, list[dict[str, Any]]],
    catalog_name: str,
    value: str | None,
) -> dict[str, Any] | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    for item in catalog[catalog_name]:
        if _normalize_text(item["name"]) == normalized:
            return item

    return None


def _merge_drafts(
    base: AgentSetupDraft | None,
    patch: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = base.model_dump() if base else {}
    for key, value in (patch or {}).items():
        if value is None:
            continue
        if key == "tobaccos" and not value:
            continue
        merged[key] = value
    return merged


def _normalize_tobaccos(
    draft: AgentSetupDraft,
    catalog: dict[str, list[dict[str, Any]]],
    valid_ids: set[str],
) -> None:
    by_id = {item["id"]: item for item in catalog["tobaccos"]}
    normalized_tobaccos = []
    seen_ids = set()

    for item in draft.tobaccos:
        selected = by_id.get(item.tobacco_id) if item.tobacco_id else None
        if not selected:
            selected = _catalog_item_by_name(catalog, "tobaccos", item.tobacco_name)
        if not selected or selected["id"] not in valid_ids:
            continue
        if selected["id"] in seen_ids:
            continue
        seen_ids.add(selected["id"])
        item.tobacco_id = selected["id"]
        item.tobacco_name = selected["name"]
        normalized_tobaccos.append(item)

    draft.tobaccos = normalized_tobaccos
    if not draft.tobaccos:
        return

    provided_total = sum(item.percentage or 0 for item in draft.tobaccos)
    if provided_total <= 0:
        base = 100 // len(draft.tobaccos)
        remainder = 100 - base * len(draft.tobaccos)
        for index, item in enumerate(draft.tobaccos):
            item.percentage = base + (remainder if index == 0 else 0)
        return

    normalized: list[int] = []
    for item in draft.tobaccos:
        value = max(1, round(((item.percentage or 0) / provided_total) * 100))
        normalized.append(value)

    diff = 100 - sum(normalized)
    normalized[0] = max(1, normalized[0] + diff)
    for item, value in zip(draft.tobaccos, normalized, strict=False):
        item.percentage = min(100, max(1, value))


def _sanitize_draft(
    raw_draft: dict[str, Any] | None,
    catalog: dict[str, list[dict[str, Any]]],
) -> AgentSetupDraft:
    draft = AgentSetupDraft.model_validate(raw_draft or {})
    ids = _catalog_ids(catalog)

    for field_name, name_field, catalog_name in (
        ("bowl_id", "bowl_name", "bowls"),
        ("kaloud_id", "kaloud_name", "kalouds"),
        ("coal_id", "coal_name", "coals"),
        ("coal_placement_id", "coal_placement_name", "coal_placements"),
        ("bowl_setup_type_id", "bowl_setup_type_name", "bowl_setup_types"),
    ):
        by_id = {item["id"]: item for item in catalog[catalog_name]}
        selected_id = getattr(draft, field_name)
        selected = by_id.get(selected_id) if selected_id else None
        if not selected:
            selected = _catalog_item_by_name(catalog, catalog_name, getattr(draft, name_field))
        if selected and selected["id"] in ids[catalog_name]:
            setattr(draft, field_name, selected["id"])
            setattr(draft, name_field, selected["name"])
        else:
            setattr(draft, field_name, None)
            setattr(draft, name_field, None)

    _normalize_tobaccos(draft, catalog, ids["tobaccos"])
    return draft


def _rate_limit_key(request: Request, user: User | None) -> str:
    if user:
        return str(user.id)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "anonymous"


def _enforce_agent_rate_limit(request: Request, user: User | None) -> None:
    limit = max(1, settings.AGENT_RATE_LIMIT_PER_MINUTE)
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=1)
    bucket = _rate_limits[_rate_limit_key(request, user)]
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many agent requests. Please try again later.",
        )
    bucket.append(now)


def _fill_equipment_defaults(
    draft: AgentSetupDraft,
    catalog: dict[str, list[dict[str, Any]]],
) -> AgentSetupDraft:
    for id_field, name_field, catalog_name in (
        ("bowl_id", "bowl_name", "bowls"),
        ("kaloud_id", "kaloud_name", "kalouds"),
        ("coal_id", "coal_name", "coals"),
        ("coal_placement_id", "coal_placement_name", "coal_placements"),
        ("bowl_setup_type_id", "bowl_setup_type_name", "bowl_setup_types"),
    ):
        items = catalog[catalog_name]
        if not items:
            continue

        by_id = {item["id"]: item for item in items}
        selected_id = getattr(draft, id_field)
        selected = by_id.get(selected_id) if selected_id else items[0]

        setattr(draft, id_field, selected["id"])
        setattr(draft, name_field, selected["name"])

    return draft


def _missing_fields(draft: AgentSetupDraft) -> list[str]:
    missing = [
        label
        for field_name, label in REQUIRED_FIELDS.items()
        if not getattr(draft, field_name)
    ]
    if not draft.tobaccos:
        missing.append("хотя бы один табак")
    return missing


async def _ask_openrouter(
    request: AgentChatRequest,
    catalog: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENROUTER_API_KEY is not configured",
        )

    user_payload = {
        "catalog": catalog,
        "current_draft": request.draft.model_dump() if request.draft else None,
        "messages": [message.model_dump() for message in request.messages],
    }

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": settings.API_PUBLIC_URL or "https://shisha-guid.api-api-api.com",
                    "X-Title": "ShishaGuid setup agent",
                },
                json={
                    "model": settings.OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps(user_payload, ensure_ascii=False),
                        },
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                },
            )
    except httpx.HTTPError as exc:
        logger.exception("OpenRouter request transport failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter request failed",
        ) from exc

    if response.status_code >= 400:
        logger.warning(
            "OpenRouter request failed",
            extra={"status_code": response.status_code, "body": response.text[:500]},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter request failed",
        )

    try:
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_json_object(content)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.exception("OpenRouter returned invalid response")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter returned invalid response",
        ) from exc


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_setup_agent(
    request: AgentChatRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
):
    _enforce_agent_rate_limit(http_request, user)
    catalog = await _load_catalog(db)

    if request.publish:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to publish setup",
                headers={"WWW-Authenticate": "Bearer"},
            )
        draft = _sanitize_draft(
            request.draft.model_dump() if request.draft else None,
            catalog,
        )
        draft = _fill_equipment_defaults(draft, catalog)
        missing = _missing_fields(draft)
        if missing:
            return AgentChatResponse(
                reply=f"Пока нельзя опубликовать: не хватает {', '.join(missing)}.",
                draft=draft,
                needs_confirmation=True,
            )

        setup = await crud.create_setup(
            db,
            BowlSetupCreate(
                name=draft.name or "Новая забивка",
                description=draft.description,
                bowl_id=draft.bowl_id,
                kaloud_id=draft.kaloud_id,
                coal_id=draft.coal_id,
                coal_placement_id=draft.coal_placement_id,
                bowl_setup_type_id=draft.bowl_setup_type_id,
                tobaccos=[
                    BowlSetupTobaccoCreate(
                        tobacco_id=item.tobacco_id,
                        percentage=item.percentage or 1,
                    )
                    for item in draft.tobaccos
                    if item.tobacco_id
                ],
            ),
            user.id,
        )
        return AgentChatResponse(
            reply=f"Готово, опубликовал забивку «{setup.name}».",
            draft=draft,
            created_setup_id=str(setup.id),
        )

    agent_result = await _ask_openrouter(request, catalog)
    draft = _sanitize_draft(_merge_drafts(request.draft, agent_result.get("draft")), catalog)
    missing = _missing_fields(draft)
    action = agent_result.get("action")
    reply = str(agent_result.get("reply") or "").strip()

    return AgentChatResponse(
        reply=reply,
        draft=draft,
        needs_confirmation=not missing and action in {"confirm", "create_setup"},
    )


@router.get("/capabilities")
async def get_agent_capabilities():
    return {
        "voice_transcription": bool(settings.OPENAI_API_KEY),
        "message_limit": 20,
    }


@router.post("/transcribe", response_model=AgentTranscribeResponse)
async def transcribe_setup_voice(
    file: UploadFile,
    user: User = Depends(get_current_user),
):
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            data={"model": settings.OPENAI_TRANSCRIBE_MODEL},
            files={
                "file": (
                    file.filename or "voice.webm",
                    content,
                    file.content_type or "audio/webm",
                )
            },
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI transcription request failed",
        )

    data = response.json()
    return AgentTranscribeResponse(text=data.get("text", ""))
