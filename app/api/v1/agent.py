import json
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
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

CATALOG_LIMIT = 80

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
Твоя задача: собрать черновик забивки из текста пользователя, сверить его с каталогом
и попросить подтверждение перед созданием.

Правила:
- Используй только id из переданного каталога. Не выдумывай id.
- Если пользователь назвал сущность, выбери самый близкий элемент каталога.
- Если нужного элемента нет в каталоге, спроси уточнение и не создавай забивку.
- Если проценты табаков не указаны, распредели табаки поровну.
- Создавай только после явного подтверждения пользователя: "да", "подтверждаю",
  "создавай", "добавляй" или похожее.
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
    result = await db.execute(
        select(model).order_by(func.lower(model.name)).limit(CATALOG_LIMIT)
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


def _normalize_tobaccos(draft: AgentSetupDraft, valid_ids: set[str]) -> None:
    draft.tobaccos = [
        item
        for item in draft.tobaccos
        if item.tobacco_id and item.tobacco_id in valid_ids
    ]
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

    for field_name, catalog_name in (
        ("bowl_id", "bowls"),
        ("kaloud_id", "kalouds"),
        ("coal_id", "coals"),
        ("coal_placement_id", "coal_placements"),
        ("bowl_setup_type_id", "bowl_setup_types"),
    ):
        value = getattr(draft, field_name)
        if value and value not in ids[catalog_name]:
            setattr(draft, field_name, None)

    _normalize_tobaccos(draft, ids["tobaccos"])
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

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter request failed",
        )

    content = response.json()["choices"][0]["message"]["content"]
    return _parse_json_object(content)


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_setup_agent(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    catalog = await _load_catalog(db)
    agent_result = await _ask_openrouter(request, catalog)
    draft = _sanitize_draft(agent_result.get("draft"), catalog)
    missing = _missing_fields(draft)
    action = agent_result.get("action")
    reply = str(agent_result.get("reply") or "").strip()

    if action == "create_setup" and not missing:
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
            reply=reply or f"Готово, добавил забивку «{setup.name}».",
            draft=draft,
            created_setup_id=str(setup.id),
        )

    if missing:
        missing_text = ", ".join(missing)
        reply = reply or f"Не хватает данных: {missing_text}. Напиши их в чат."
        return AgentChatResponse(reply=reply, draft=draft)

    return AgentChatResponse(
        reply=reply or "Проверь данные. Если все верно, напиши «да, добавляй».",
        draft=draft,
        needs_confirmation=action == "confirm",
    )


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
