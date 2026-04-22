
from fastapi import APIRouter
from app.services.oauth_service import OAuthService

router = APIRouter(prefix="/integrations")
oauth = OAuthService()

@router.get("/gmail")
def gmail():
    return {"status": oauth.connect_gmail()}

@router.get("/calendar")
def calendar():
    return {"status": oauth.connect_calendar()}

@router.get("/slack")
def slack():
    return {"status": oauth.connect_slack()}
