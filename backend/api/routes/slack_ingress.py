"""
Slack Events API — inbound messages trigger the INFERA pipeline.

Slack app setup (summary):
1. Create a Slack app → enable Event Subscriptions → Request URL: https://<your-host>/webhooks/slack/events
2. Subscribe to bot events: `message.channels` (public) and/or `message.groups` (private), or `message.im`
3. Install app to workspace; copy Signing Secret → SLACK_SIGNING_SECRET
4. Invite the bot to the target channel

Message format (recommended):
  Competitor: Acme Inc
  Acme launched ProductX — assess impact on our roadmap.

If `Competitor:` is omitted, Sentinel infers entities from the text.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_database
from backend.core.config import settings
from backend.core.database import AsyncSessionLocal
from backend.core.logger import get_logger
from backend.models.schemas import SignalInput
from backend.models.tables import WebhookEvent
from backend.pipeline.executor import dispatch_pipeline

logger = get_logger("slack_ingress")

router = APIRouter()

_SLACK_LINK = re.compile(r"<(https?://[^|>]+)\|([^>]+)>")
_SLACK_BARE_URL = re.compile(r"<(https?://[^>]+)>")
_SLACK_USER = re.compile(r"<@[A-Z0-9]+>")
_SLACK_CHANNEL = re.compile(r"<#[A-Z0-9]+\|([^>]+)>")
_COMPETITOR_LINE = re.compile(r"^(?:competitor|company)\s*:\s*(.+)\s*$", re.IGNORECASE)


def _slack_channel_allowlist() -> set[str]:
    raw = (settings.SLACK_INGRESS_CHANNEL_IDS or "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def _plain_text_from_slack(raw: str) -> str:
    if not raw:
        return ""
    text = _SLACK_USER.sub("", raw)
    text = _SLACK_CHANNEL.sub(r"\1", text)
    text = _SLACK_LINK.sub(r"\2 (\1)", text)
    text = _SLACK_BARE_URL.sub(r"\1", text)
    return text.strip()


def _competitor_and_body(text: str) -> tuple[str | None, str]:
    competitor: str | None = None
    kept: list[str] = []
    for line in text.splitlines():
        m = _COMPETITOR_LINE.match(line.strip())
        if m:
            competitor = m.group(1).strip()
            continue
        kept.append(line)
    body = "\n".join(kept).strip()
    return competitor, body


def _slack_payload_to_signal(event: dict[str, Any]) -> SignalInput | None:
    subtype = event.get("subtype")
    if subtype in ("bot_message", "message_changed", "message_deleted", "channel_join", "channel_leave"):
        return None
    if event.get("bot_id") or event.get("app_id"):
        return None

    raw_text = event.get("text") or ""
    plain = _plain_text_from_slack(raw_text)
    if not plain:
        return None

    competitor, body = _competitor_and_body(plain)
    # Title = first substantive line or truncated blob
    first_line = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
    title = (first_line[:200] if first_line else plain[:200]) or "Slack competitive signal"
    slack_ts = event.get("ts") or ""
    channel = event.get("channel") or ""

    permalink_hint = f"slack:{channel}:{slack_ts}" if channel and slack_ts else None

    return SignalInput(
        title=title,
        source="slack",
        url=permalink_hint,
        content=body or plain,
        competitor_name=competitor,
        custom_question=(
            "From this Slack signal: assess competitive impact, urgency, "
            "and recommended actions for our leadership team."
        ),
    )


def _verify_slack_signature(*, body: bytes, timestamp: str, signature: str, signing_secret: str) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        ts_int = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts_int) > 60 * 5:
        return False

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/webhooks/slack/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_database),
) -> dict[str, Any]:
    """
    Slack Events API endpoint — URL verification and `message` events.
    """
    raw_body = await request.body()
    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")
    secret = (settings.SLACK_SIGNING_SECRET or "").strip()

    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack ingress not configured (set SLACK_SIGNING_SECRET)",
        )

    if not _verify_slack_signature(body=raw_body, timestamp=ts, signature=sig, signing_secret=secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    if payload.get("type") != "event_callback":
        return {"ok": True}

    event = payload.get("event") or {}
    if event.get("type") != "message":
        return {"ok": True}

    allow = _slack_channel_allowlist()
    ch = event.get("channel") or ""
    if allow and ch not in allow:
        logger.info("slack_ingress_channel_ignored", channel=ch)
        return {"ok": True}

    signal = _slack_payload_to_signal(event)
    if signal is None:
        return {"ok": True}

    webhook = WebhookEvent(
        source="slack",
        title=signal.title,
        url=signal.url,
        payload=signal.model_dump(mode="json", exclude_none=True),
    )
    session.add(webhook)
    await session.commit()
    await session.refresh(webhook)

    background_tasks.add_task(
        dispatch_pipeline,
        webhook.id,
        signal.model_dump(mode="json", exclude_none=True),
    )
    logger.info(
        "slack_ingress_pipeline_queued",
        webhook_id=webhook.id,
        channel=ch,
        title=signal.title[:80],
    )
    return {"ok": True}
