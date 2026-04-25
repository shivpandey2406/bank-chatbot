"""
MCP Service — Gmail, Google Calendar, Slack tool integrations.
Tokens are persisted to SQLite via the Token model.
Google tokens auto-refresh on 401.
All MCP actions are logged for audit.
"""

import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Thread pool for running async MCP calls from sync agent code
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def run_async(coro):
    """Run an async coroutine from synchronous code safely.
    Works even when called inside an already-running event loop
    (e.g. from a sync LangGraph node inside FastAPI).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an active event loop — run in a new thread
        future = _executor.submit(asyncio.run, coro)
        return future.result(timeout=30)
    else:
        return asyncio.run(coro)


# ── Token persistence (SQLite-backed) ───────────────────────────────

async def store_tokens(user_id: str, provider: str, tokens: Dict[str, Any]):
    """Persist OAuth tokens to the database (upsert by user_id + provider)."""
    from app.db.session import AsyncSessionLocal
    from app.models.token import Token
    from sqlalchemy import select

    access_token = tokens.get("access_token") or tokens.get("authed_user", {}).get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    async with AsyncSessionLocal() as session:
        stmt = select(Token).where(
            Token.user_id == 1,
            Token.oauth_provider == provider,
            Token.token == f"oauth_{provider}_{user_id}",
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.oauth_access_token = access_token
            if refresh_token:
                existing.oauth_refresh_token = refresh_token
            existing.is_active = True
        else:
            new_token = Token()
            new_token.user_id = 1
            new_token.token = f"oauth_{provider}_{user_id}"
            new_token.token_type = "oauth"
            new_token.oauth_provider = provider
            new_token.oauth_access_token = access_token
            new_token.oauth_refresh_token = refresh_token
            new_token.is_active = True
            new_token.is_revoked = False
            session.add(new_token)

        await session.commit()
    logger.info("Stored OAuth tokens", provider=provider, user_id=user_id)


async def get_tokens(user_id: str, provider: str) -> Optional[Dict[str, Any]]:
    """Retrieve stored OAuth tokens from the database."""
    from app.db.session import AsyncSessionLocal
    from app.models.token import Token
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(Token).where(
            Token.oauth_provider == provider,
            Token.token == f"oauth_{provider}_{user_id}",
            Token.is_active == True,
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return {
                "access_token": row.oauth_access_token,
                "refresh_token": row.oauth_refresh_token or "",
            }
    return None


async def get_any_tokens(provider: str) -> Optional[Dict[str, Any]]:
    """Get the first active token for a provider (any user)."""
    from app.db.session import AsyncSessionLocal
    from app.models.token import Token
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(Token).where(
            Token.oauth_provider == provider,
            Token.is_active == True,
        ).limit(1)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return {
                "access_token": row.oauth_access_token,
                "refresh_token": row.oauth_refresh_token or "",
                "token_key": row.token,
            }
    return None


async def _refresh_and_retry_google(refresh_token: str, token_key: str) -> Optional[str]:
    """Refresh a Google token and update the DB. Returns new access_token or None."""
    from app.services.oauth_service import OAuthService
    from app.db.session import AsyncSessionLocal
    from app.models.token import Token
    from sqlalchemy import select

    try:
        logger.info("Attempting Google token refresh", token_key=token_key)
        new_tokens = await OAuthService.refresh_google_token(refresh_token)
        new_access = new_tokens.get("access_token")
        if not new_access:
            logger.error("Google token refresh returned no access_token")
            return None
        async with AsyncSessionLocal() as session:
            stmt = select(Token).where(Token.token == token_key)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                row.oauth_access_token = new_access
                if new_tokens.get("refresh_token"):
                    row.oauth_refresh_token = new_tokens["refresh_token"]
                await session.commit()
        logger.info("Google token refreshed successfully", token_key=token_key)
        return new_access
    except Exception as e:
        logger.error("Google token refresh failed", error=str(e))
        return None


async def has_connected_provider(provider: str) -> bool:
    """Check if any user has connected a given provider."""
    return (await get_any_tokens(provider)) is not None


# ── Audit logging helper ────────────────────────────────────────────

def _audit_log(action: str, success: bool, detail: str = ""):
    """Log every MCP tool invocation for audit trail."""
    level = "info" if success else "error"
    getattr(logger, level)(
        "MCP_AUDIT",
        action=action,
        success=success,
        detail=detail[:500],
    )


# ── MCP Tool Execution Layer ────────────────────────────────────────

class MCPService:
    """External tool execution layer with auto-refresh for Google APIs."""

    @staticmethod
    async def send_email(
        access_token: str, to: str, subject: str, body: str,
        refresh_token: str = "", token_key: str = "",
    ) -> Dict[str, Any]:
        import httpx, base64
        logger.info("MCP: send_email", to=to, subject=subject[:80])
        raw = f"To: {to}\r\nSubject: {subject}\r\n"
        raw += f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}"
        encoded = base64.urlsafe_b64encode(raw.encode()).decode()

        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": encoded},
            )
            if r.status_code == 401 and refresh_token:
                logger.info("Gmail 401 — attempting token refresh")
                new_token = await _refresh_and_retry_google(refresh_token, token_key)
                if new_token:
                    r = await c.post(
                        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                        headers={"Authorization": f"Bearer {new_token}"},
                        json={"raw": encoded},
                    )
            ok = r.status_code == 200
            result = {"success": ok, "id": r.json().get("id")} if ok else {"success": False, "error": r.text}
            _audit_log("send_email", ok, f"to={to} status={r.status_code}")
            return result

    @staticmethod
    async def read_emails(
        access_token: str, n: int = 5,
        refresh_token: str = "", token_key: str = "",
    ) -> Dict[str, Any]:
        import httpx
        logger.info("MCP: read_emails", count=n)
        url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={n}"
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url, headers={"Authorization": f"Bearer {access_token}"})
            if r.status_code == 401 and refresh_token:
                new_token = await _refresh_and_retry_google(refresh_token, token_key)
                if new_token:
                    r = await c.get(url, headers={"Authorization": f"Bearer {new_token}"})
            ok = r.status_code == 200
            result = {"success": ok, "messages": r.json().get("messages", [])} if ok else {"success": False, "error": r.text}
            _audit_log("read_emails", ok, f"status={r.status_code}")
            return result

    @staticmethod
    async def create_calendar_event(
        access_token: str, summary: str, start: str, end: str,
        description: str = "", attendees: Optional[List[str]] = None,
        refresh_token: str = "", token_key: str = "",
    ) -> Dict[str, Any]:
        import httpx
        logger.info("MCP: create_calendar_event", summary=summary, start=start)
        event: Dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        if attendees:
            event["attendees"] = [{"email": e} for e in attendees]

        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(url, headers={"Authorization": f"Bearer {access_token}"}, json=event)
            if r.status_code == 401 and refresh_token:
                logger.info("Calendar 401 — attempting token refresh")
                new_token = await _refresh_and_retry_google(refresh_token, token_key)
                if new_token:
                    r = await c.post(url, headers={"Authorization": f"Bearer {new_token}"}, json=event)
            ok = r.status_code == 200
            result = {"success": ok, "event_id": r.json().get("id")} if ok else {"success": False, "error": r.text}
            _audit_log("create_calendar_event", ok, f"summary={summary} status={r.status_code}")
            return result

    @staticmethod
    async def send_slack_message(
        token: Optional[str] = None, channel: Optional[str] = None, text: str = "",
    ) -> Dict[str, Any]:
        import httpx
        bot_token = token or settings.slack_bot_token
        ch = channel or settings.slack_channel_id
        logger.info("MCP: send_slack_message", channel=ch)
        if not bot_token:
            _audit_log("send_slack_message", False, "no token available")
            return {"success": False, "error": "Slack token not available. Connect via /api/oauth/slack/login or set SLACK_BOT_TOKEN."}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}"},
                json={"channel": ch, "text": text},
            )
            data = r.json()
            ok = data.get("ok", False)
            result = {"success": ok, "error": data.get("error")}
            _audit_log("send_slack_message", ok, f"channel={ch} error={data.get('error')}")
            return result
