"""
OAuth Service
Google OAuth2 and Slack OAuth integration.
"""

from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OAuthService:
    """Handles OAuth2 flows for Google and Slack."""

    # ── Google OAuth2 ────────────────────────────────────────────────
    @staticmethod
    def get_google_auth_url() -> str:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID not configured")
        scopes = "openid email profile https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar"
        return (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={settings.google_client_id}"
            f"&redirect_uri={settings.google_redirect_uri}"
            f"&response_type=code"
            f"&scope={scopes}"
            f"&access_type=offline&prompt=consent"
        )

    @staticmethod
    async def exchange_google_code(code: str) -> Dict[str, Any]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            })
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def refresh_google_token(refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired Google access token."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            })
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def get_google_user_info(access_token: str) -> Dict[str, Any]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Slack OAuth ──────────────────────────────────────────────────
    @staticmethod
    def get_slack_auth_url() -> str:
        if not settings.slack_client_id:
            raise ValueError("SLACK_CLIENT_ID not configured")
        scopes = "chat:write,channels:read,groups:read,im:write"
        return (
            "https://slack.com/oauth/v2/authorize?"
            f"client_id={settings.slack_client_id}"
            f"&scope={scopes}"
            f"&redirect_uri={settings.slack_redirect_uri}"
        )

    @staticmethod
    async def exchange_slack_code(code: str) -> Dict[str, Any]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://slack.com/api/oauth.v2.access", data={
                "code": code,
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "redirect_uri": settings.slack_redirect_uri,
            })
            resp.raise_for_status()
            return resp.json()
