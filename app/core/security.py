"""
Security Module
Handles authentication, authorization, and security utilities
"""

from datetime import datetime, timedelta
from typing import Optional, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


class SecurityManager:
    """
    Centralized security management class.
    Handles password hashing, token creation, and token verification.
    """

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a plain password."""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.

        Args:
            data: Dictionary containing token payload data
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access_token"
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm
        )
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """
        Decode and verify a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm]
            )
            return payload
        except JWTError:
            return None

    @staticmethod
    def validate_token(token: str) -> dict:
        """
        Validate a JWT token and return the payload.

        Args:
            token: JWT token string

        Returns:
            Token payload dictionary

        Raises:
            HTTPException: If token is invalid or expired
        """
        payload = SecurityManager.decode_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_type = payload.get("type")
        if token_type != "access_token":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)
) -> Optional[dict]:
    """
    Dependency to get current authenticated user from token.

    Supports both OAuth2 and Bearer token authentication.
    Returns None if no token is provided (for public endpoints).
    """
    # Try OAuth2 token first
    if token is None and bearer is not None:
        token = bearer.credentials

    if token is None:
        return None

    try:
        payload = SecurityManager.validate_token(token)
        return payload
    except HTTPException:
        return None


async def get_current_active_user(
    current_user: Optional[dict] = Depends(get_current_user)
) -> dict:
    """
    Dependency to get current active user.
    Raises exception if user is not authenticated.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_auth(request: Request) -> bool:
    """
    Check if an endpoint requires authentication.
    Can be used to configure which endpoints need auth.
    """
    # Public endpoints that don't require auth
    public_paths = [
        "/",
        "/health",
        f"{settings.api_prefix}/health",
        f"{settings.api_prefix}/auth/login",
        f"{settings.api_prefix}/auth/register",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]

    path = request.url.path.rstrip("/")
    return path not in public_paths


class RateLimiter:
    """
    Simple in-memory rate limiter.
    For production, use Redis-based rate limiting.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[datetime]] = {}

    def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed for the given key."""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)

        if key not in self._requests:
            self._requests[key] = []

        # Remove old requests
        self._requests[key] = [
            req_time for req_time in self._requests[key]
            if req_time > window_start
        ]

        if len(self._requests[key]) >= self.max_requests:
            return False

        self._requests[key].append(now)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


async def create_default_user():
    """
    Create a default user if one doesn't exist.
    This is a placeholder for initial setup.
    """
    pass


def verify_token(token: str) -> Optional[dict]:
    """
    Verify a JWT token and return the payload.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    return SecurityManager.decode_token(token)