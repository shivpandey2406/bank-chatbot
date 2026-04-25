"""
Tool Router — Detects action intent from user messages and dispatches
to the appropriate MCP tool with stored user tokens.
"""

import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.core.logging import get_logger
from app.services.mcp_service import MCPService, get_any_tokens

logger = get_logger(__name__)


def detect_tool_intent(query: str) -> Optional[Dict[str, Any]]:
    """
    Detect which MCP tool the user wants and extract parameters.
    Returns None if no actionable tool intent is found.
    """
    q = query.lower().strip()

    # ── Email intent ─────────────────────────────────────────────
    email_match = re.search(
        r'(?:send|write|compose|draft)\s+(?:an?\s+)?email\s+to\s+([\w.\-+]+@[\w.\-]+)',
        q,
    )
    if email_match:
        to = email_match.group(1)
        subject = _extract_quoted(query, "subject") or _extract_after(q, "subject") or "Message from Banking Chatbot"
        body = _extract_quoted(query, "body") or _extract_quoted(query, "message") or _extract_after(q, "saying") or "Sent via Banking Chatbot"
        return {"tool": "send_email", "params": {"to": to, "subject": subject, "body": body}}

    if re.search(r'\b(send|write|compose)\b.*\bemail\b', q) or re.search(r'\bemail\b.*\b(send|write)\b', q):
        return {"tool": "send_email", "params": {"to": "", "subject": "", "body": ""}, "needs_details": True}

    # ── Slack intent ─────────────────────────────────────────────
    slack_match = re.search(
        r'(?:send|post)\s+(?:a\s+)?(?:slack\s+)?message\s+(?:to\s+)?(?:#)?([\w\-]+)',
        q,
    )
    if not slack_match:
        slack_match = re.search(r'(?:post|send)\s+(?:to|on)\s+slack', q)
    if slack_match or re.search(r'\bslack\b.*\b(send|post|message)\b', q):
        channel = slack_match.group(1) if slack_match and slack_match.lastindex else None
        text = _extract_quoted(query, "message") or _extract_quoted(query, "saying") or _extract_after(q, "saying") or ""
        return {"tool": "send_slack", "params": {"channel": channel, "text": text}}

    # ── Calendar intent ──────────────────────────────────────────
    cal_patterns = [
        r'(?:create|schedule|book|set up)\s+(?:a\s+)?(?:meeting|event|appointment|calendar event)',
        r'(?:meeting|event|appointment)\s+(?:at|on|for)\s+',
    ]
    if any(re.search(p, q) for p in cal_patterns):
        summary = _extract_quoted(query, "title") or _extract_quoted(query, "summary") or _extract_after(q, "called") or "Meeting"
        time_match = re.search(r'(?:at|for)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', q)
        start_str = ""
        end_str = ""
        if time_match:
            raw_time = time_match.group(1).strip()
            start_dt = _parse_time(raw_time)
            if start_dt:
                start_str = start_dt.isoformat()
                end_str = (start_dt + timedelta(hours=1)).isoformat()
        attendees_match = re.search(r'with\s+([\w.\-+@,\s]+)', q)
        attendees = []
        if attendees_match:
            attendees = [a.strip() for a in attendees_match.group(1).split(",") if "@" in a]
        return {
            "tool": "create_calendar_event",
            "params": {
                "summary": summary,
                "start": start_str,
                "end": end_str,
                "attendees": attendees,
            },
        }

    return None


async def execute_tool(intent: Dict[str, Any], user_id: str = "default") -> Dict[str, Any]:
    """Execute the detected tool using stored tokens. Fully async."""
    tool = intent["tool"]
    params = intent["params"]
    logger.info("Executing MCP tool", tool=tool, params_keys=list(params.keys()))

    try:
        if tool == "send_email":
            token_data = await get_any_tokens("google")
            if not token_data:
                return {"success": False, "error": "Google account not connected. Please connect via /api/oauth/google/login"}
            if not params.get("to"):
                return {"success": False, "error": "Recipient email address is required."}
            return await MCPService.send_email(
                access_token=token_data["access_token"],
                to=params["to"],
                subject=params.get("subject", "Message from Banking Chatbot"),
                body=params.get("body", "Sent via Banking Chatbot"),
                refresh_token=token_data.get("refresh_token", ""),
                token_key=token_data.get("token_key", ""),
            )

        if tool == "send_slack":
            token_data = await get_any_tokens("slack")
            slack_token = token_data["access_token"] if token_data else None
            return await MCPService.send_slack_message(
                token=slack_token,
                channel=params.get("channel"),
                text=params.get("text") or "Alert from Banking Chatbot",
            )

        if tool == "create_calendar_event":
            token_data = await get_any_tokens("google")
            if not token_data:
                return {"success": False, "error": "Google account not connected. Please connect via /api/oauth/google/login"}
            if not params.get("start"):
                return {"success": False, "error": "Could not determine meeting time. Please specify a date and time."}
            return await MCPService.create_calendar_event(
                access_token=token_data["access_token"],
                summary=params.get("summary", "Meeting"),
                start=params["start"],
                end=params.get("end", params["start"]),
                attendees=params.get("attendees"),
                refresh_token=token_data.get("refresh_token", ""),
                token_key=token_data.get("token_key", ""),
            )

        return {"success": False, "error": f"Unknown tool: {tool}"}
    except Exception as e:
        logger.exception("MCP tool execution failed", tool=tool, error=str(e))
        return {"success": False, "error": f"Tool execution error: {e}"}


def execute_tool_sync(intent: Dict[str, Any], user_id: str = "default") -> Dict[str, Any]:
    """Synchronous wrapper for execute_tool.
    Safe to call from sync LangGraph nodes running inside FastAPI's event loop.
    """
    from app.services.mcp_service import run_async
    return run_async(execute_tool(intent, user_id))


# ── Helpers ──────────────────────────────────────────────────────────

def _extract_quoted(text: str, key: str) -> Optional[str]:
    m = re.search(rf'{key}\s*[=:]\s*["\'](.+?)["\']', text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_after(text: str, keyword: str) -> Optional[str]:
    m = re.search(rf'{keyword}\s+["\']?(.+?)["\']?\s*$', text, re.IGNORECASE)
    return m.group(1).strip().strip("\"'") if m else None


def _parse_time(raw: str) -> Optional[datetime]:
    """Parse a simple time string into a datetime for today."""
    from datetime import date
    raw = raw.strip().lower().replace(" ", "")
    for fmt in ("%I:%M%p", "%I%p", "%H:%M"):
        try:
            t = datetime.strptime(raw, fmt).time()
            return datetime.combine(date.today(), t)
        except ValueError:
            continue
    return None
