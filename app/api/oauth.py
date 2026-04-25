"""
OAuth API
Google and Slack OAuth2 endpoints with error handling and HTML callback UX.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.oauth_service import OAuthService
from app.services.mcp_service import store_tokens, has_connected_provider

logger = get_logger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["OAuth"])

FRONTEND_URL = settings.frontend_url


def _success_html(provider: str, detail: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>OAuth Success</title>
<style>body{{font-family:Arial,sans-serif;display:flex;justify-content:center;
align-items:center;min-height:100vh;margin:0;background:#f0fdf4}}
.card{{background:#fff;border-radius:12px;padding:40px;box-shadow:0 2px 12px rgba(0,0,0,.1);
text-align:center;max-width:420px}}
.ok{{color:#166534;font-size:1.3em;margin-bottom:8px}}
a{{display:inline-block;margin-top:16px;padding:10px 24px;background:#2563eb;
color:#fff;border-radius:8px;text-decoration:none}}</style></head>
<body><div class="card">
<div class="ok">&#10003; {provider} Connected</div>
<p>{detail}</p>
<a href="{FRONTEND_URL}">Back to Chatbot</a>
</div></body></html>"""


def _error_html(provider: str, error: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>OAuth Error</title>
<style>body{{font-family:Arial,sans-serif;display:flex;justify-content:center;
align-items:center;min-height:100vh;margin:0;background:#fef2f2}}
.card{{background:#fff;border-radius:12px;padding:40px;box-shadow:0 2px 12px rgba(0,0,0,.1);
text-align:center;max-width:420px}}
.err{{color:#991b1b;font-size:1.3em;margin-bottom:8px}}
a{{display:inline-block;margin-top:16px;padding:10px 24px;background:#2563eb;
color:#fff;border-radius:8px;text-decoration:none}}</style></head>
<body><div class="card">
<div class="err">&#10007; {provider} Connection Failed</div>
<p>{error}</p>
<a href="{FRONTEND_URL}">Back to Chatbot</a>
</div></body></html>"""


# ── Google ───────────────────────────────────────────────────────────
@router.get("/google/login")
async def google_login():
    """Redirect browser to Google OAuth consent screen."""
    try:
        url = OAuthService.get_google_auth_url()
        logger.info("Redirecting to Google OAuth", redirect_uri=settings.google_redirect_uri)
        return RedirectResponse(url)
    except ValueError as e:
        logger.error("Google OAuth login failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/google/callback")
async def google_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """Handle Google OAuth callback — exchange code for tokens."""
    logger.info("Google OAuth callback received", has_code=bool(code), error=error)

    if error:
        logger.warning("Google OAuth denied by user", error=error)
        return HTMLResponse(_error_html("Google", f"Authorization denied: {error}"))

    if not code:
        logger.error("Google OAuth callback missing code parameter")
        return HTMLResponse(_error_html("Google", "No authorization code received. Please try again."), status_code=400)

    try:
        logger.info("Exchanging Google authorization code for tokens")
        tokens = await OAuthService.exchange_google_code(code)
        user_info = await OAuthService.get_google_user_info(tokens["access_token"])
        user_id = user_info.get("id", "default")
        await store_tokens(user_id, "google", tokens)
        email = user_info.get("email", "unknown")
        logger.info("Google OAuth completed successfully", email=email, user_id=user_id)
        return HTMLResponse(_success_html("Google", f"Signed in as {email}. You can close this tab."))
    except Exception as e:
        logger.exception("Google OAuth token exchange failed", error=str(e))
        return HTMLResponse(_error_html("Google", str(e)))


# ── Slack ────────────────────────────────────────────────────────────
@router.get("/slack/login")
async def slack_login():
    """Redirect browser to Slack OAuth consent screen."""
    try:
        url = OAuthService.get_slack_auth_url()
        logger.info("Redirecting to Slack OAuth", redirect_uri=settings.slack_redirect_uri)
        return RedirectResponse(url)
    except ValueError as e:
        logger.error("Slack OAuth login failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/slack/callback")
async def slack_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """Handle Slack OAuth callback — exchange code for tokens."""
    logger.info("Slack OAuth callback received", has_code=bool(code), error=error)

    if error:
        logger.warning("Slack OAuth denied by user", error=error)
        return HTMLResponse(_error_html("Slack", f"Authorization denied: {error}"))

    if not code:
        logger.error("Slack OAuth callback missing code parameter")
        return HTMLResponse(_error_html("Slack", "No authorization code received. Please try again."), status_code=400)

    try:
        logger.info("Exchanging Slack authorization code for tokens")
        tokens = await OAuthService.exchange_slack_code(code)
        if not tokens.get("ok"):
            err_msg = tokens.get("error", "Slack OAuth failed")
            logger.error("Slack token exchange returned error", error=err_msg)
            raise ValueError(err_msg)
        team_name = tokens.get("team", {}).get("name", "workspace")
        await store_tokens("default", "slack", tokens)
        logger.info("Slack OAuth completed successfully", team=team_name)
        return HTMLResponse(_success_html("Slack", f"Connected to {team_name}. You can close this tab."))
    except Exception as e:
        logger.exception("Slack OAuth token exchange failed", error=str(e))
        return HTMLResponse(_error_html("Slack", str(e)))


# ── Status ───────────────────────────────────────────────────────────
@router.get("/status")
async def oauth_status():
    """Check which OAuth providers are configured and actually connected."""
    google_connected = await has_connected_provider("google")
    slack_connected = await has_connected_provider("slack")
    return {
        "google": {
            "configured": bool(settings.google_client_id and settings.google_client_secret),
            "connected": google_connected,
            "login_url": "/api/oauth/google/login",
        },
        "slack": {
            "configured": bool(settings.slack_client_id and settings.slack_client_secret),
            "connected": slack_connected,
            "login_url": "/api/oauth/slack/login",
        },
    }
