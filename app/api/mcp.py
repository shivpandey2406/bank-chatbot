"""
MCP Test Endpoints
Direct tool testing without going through the chat flow.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.core.logging import get_logger
from app.services.mcp_service import MCPService, get_any_tokens

logger = get_logger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["MCP Tools"])


class EmailRequest(BaseModel):
    to: str
    subject: str
    body: str


class CalendarRequest(BaseModel):
    summary: str
    start: str
    end: str
    description: str = ""
    attendees: Optional[List[str]] = None


class SlackRequest(BaseModel):
    channel: Optional[str] = None
    text: str


@router.post("/gmail/send")
async def send_gmail(req: EmailRequest):
    """Send an email via Gmail using stored Google OAuth tokens."""
    logger.info("MCP endpoint: gmail/send", to=req.to, subject=req.subject[:80])
    token_data = await get_any_tokens("google")
    if not token_data:
        raise HTTPException(status_code=401, detail="Google account not connected. Visit /api/oauth/google/login")
    result = await MCPService.send_email(
        access_token=token_data["access_token"],
        to=req.to,
        subject=req.subject,
        body=req.body,
        refresh_token=token_data.get("refresh_token", ""),
        token_key=token_data.get("token_key", ""),
    )
    if not result.get("success"):
        logger.error("MCP endpoint gmail/send failed", error=result.get("error"))
    return result


@router.post("/calendar/create")
async def create_calendar_event(req: CalendarRequest):
    """Create a Google Calendar event using stored OAuth tokens."""
    logger.info("MCP endpoint: calendar/create", summary=req.summary)
    token_data = await get_any_tokens("google")
    if not token_data:
        raise HTTPException(status_code=401, detail="Google account not connected. Visit /api/oauth/google/login")
    result = await MCPService.create_calendar_event(
        access_token=token_data["access_token"],
        summary=req.summary,
        start=req.start,
        end=req.end,
        description=req.description,
        attendees=req.attendees,
        refresh_token=token_data.get("refresh_token", ""),
        token_key=token_data.get("token_key", ""),
    )
    if not result.get("success"):
        logger.error("MCP endpoint calendar/create failed", error=result.get("error"))
    return result


@router.post("/slack/send")
async def send_slack(req: SlackRequest):
    """Send a Slack message using stored OAuth tokens or bot token."""
    logger.info("MCP endpoint: slack/send", channel=req.channel)
    token_data = await get_any_tokens("slack")
    slack_token = token_data["access_token"] if token_data else None
    result = await MCPService.send_slack_message(
        token=slack_token,
        channel=req.channel,
        text=req.text,
    )
    if not result.get("success"):
        logger.error("MCP endpoint slack/send failed", error=result.get("error"))
    return result
