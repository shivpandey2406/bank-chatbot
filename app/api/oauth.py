"""
OAuth API
Google and Slack OAuth2 endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from typing import Dict, Any

from app.core.logging import get_logger
from app.services.oauth_service import OAuthService
from app.services.mcp_service import store_tokens

logger = get_logger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["OAuth"])


# ── Google ───────────────────────────────────────────────────────────
@router.get("/google/login")
async def google_login():
    """Redirect user to Google OAuth consent screen."""
    try:
        url = OAuthService.get_google_auth_url()
        return RedirectResponse(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/google/callback")
async def google_callback(code: str = Query(...)):
    """Handle Google OAuth callback."""
    try:
        tokens = await OAuthService.exchange_google_code(code)
        user_info = await OAuthService.get_google_user_info(tokens["access_token"])
        user_id = user_info.get("id", "default")
        store_tokens(user_id, "google", tokens)
        return {
            "success": True,
            "user": user_info,
            "message": "Google account connected successfully",
        }
    except Exception as e:
        logger.exception("Google OAuth callback failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ── Slack ────────────────────────────────────────────────────────────
@router.get("/slack/login")
async def slack_login():
    """Redirect user to Slack OAuth consent screen."""
    try:
        url = OAuthService.get_slack_auth_url()
        return RedirectResponse(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/slack/callback")
async def slack_callback(code: str = Query(...)):
    """Handle Slack OAuth callback."""
    try:
        tokens = await OAuthService.exchange_slack_code(code)
        if not tokens.get("ok"):
            raise ValueError(tokens.get("error", "Slack OAuth failed"))
        store_tokens("default", "slack", tokens)
        return {
            "success": True,
            "team": tokens.get("team", {}),
            "message": "Slack workspace connected successfully",
        }
    except Exception as e:
        logger.exception("Slack OAuth callback failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ── Status ───────────────────────────────────────────────────────────
@router.get("/status")
async def oauth_status():
    """Check which OAuth providers are configured."""
    from app.core.config import settings
    return {
        "google": {
            "configured": bool(settings.google_client_id and settings.google_client_secret),
            "login_url": "/api/oauth/google/login",
        },
        "slack": {
            "configured": bool(settings.slack_client_id and settings.slack_client_secret),
            "login_url": "/api/oauth/slack/login",
        },
    }
