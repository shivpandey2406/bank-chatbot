"""
MCP Service — Gmail, Google Calendar, Slack tool integrations.
"""

from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_tokens: Dict[str, Dict[str, Any]] = {}


def store_tokens(user_id: str, provider: str, tokens: Dict[str, Any]):
    _tokens.setdefault(user_id, {})[provider] = tokens


def get_tokens(user_id: str, provider: str) -> Optional[Dict[str, Any]]:
    return _tokens.get(user_id, {}).get(provider)


class MCPService:
    """External tool execution layer."""

    @staticmethod
    async def send_email(access_token: str, to: str, subject: str, body: str) -> Dict[str, Any]:
        import httpx, base64
        raw = f"To: {to}\r\nSubject: {subject}\r\n"
        raw += f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}"
        encoded = base64.urlsafe_b64encode(raw.encode()).decode()
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": encoded},
            )
            if r.status_code == 200:
                return {"success": True, "id": r.json().get("id")}
            return {"success": False, "error": r.text}

    @staticmethod
    async def read_emails(access_token: str, n: int = 5) -> Dict[str, Any]:
        import httpx
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={n}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 200:
                return {"success": True, "messages": r.json().get("messages", [])}
            return {"success": False, "error": r.text}

    @staticmethod
    async def create_calendar_event(
        access_token: str, summary: str, start: str, end: str,
        description: str = "", attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        import httpx
        event: Dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        if attendees:
            event["attendees"] = [{"email": e} for e in attendees]
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {access_token}"},
                json=event,
            )
            if r.status_code == 200:
                return {"success": True, "event_id": r.json().get("id")}
            return {"success": False, "error": r.text}

    @staticmethod
    async def send_slack_message(
        token: Optional[str] = None, channel: Optional[str] = None, text: str = "",
    ) -> Dict[str, Any]:
        import httpx
        bot_token = token or settings.slack_bot_token
        ch = channel or settings.slack_channel_id
        if not bot_token:
            return {"success": False, "error": "Slack bot token not configured"}
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}"},
                json={"channel": ch, "text": text},
            )
            data = r.json()
            return {"success": data.get("ok", False), "error": data.get("error")}
