"""
Vigil Security Module

Provides:
- Input validation schemas (Marshmallow)
- JWT authentication decorator
- Rate limiting configuration
- CORS origin management
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Input Validation (Marshmallow)
# ---------------------------------------------------------------------------

try:
    from marshmallow import Schema, fields, validate, ValidationError
    HAS_MARSHMALLOW = True
except ImportError:
    HAS_MARSHMALLOW = False


class AlertQuerySchema(Schema):
    """Validation schema for /alerts query parameters."""
    ticker = fields.String(
        validate=validate.Length(min=1, max=10),
        load_default=None,
    )
    signal_type = fields.String(
        validate=validate.OneOf([
            "VOLUME_SPIKE_UP",
            "VOLUME_SPIKE_DOWN",
            "ACCUMULATION_DETECTED",
        ]),
        load_default=None,
    )
    state = fields.String(
        validate=validate.OneOf([
            "BREAKOUT",
            "TRENDING_UP",
            "TRENDING_DOWN",
            "RANGING",
            "ACCUMULATING",
        ]),
        load_default=None,
    )
    limit = fields.Integer(
        validate=validate.Range(min=1, max=500),
        load_default=50,
    )
    offset = fields.Integer(
        validate=validate.Range(min=0),
        load_default=0,
    )


class WatchlistSchema(Schema):
    """Validation schema for watchlist operations."""
    ticker = fields.String(
        required=True,
        validate=validate.Length(min=1, max=10),
    )


class BacktestRunSchema(Schema):
    """Validation schema for /backtest/run request body."""
    name = fields.String(load_default=None)
    start_date = fields.String(required=True)
    end_date = fields.String(required=True)
    tickers = fields.List(fields.String(), required=True)
    capital = fields.Float(load_default=100000)
    slippage_bps = fields.Float(load_default=5)
    commission_bps = fields.Float(load_default=10)


# Pre-instantiated schemas
alert_query_schema = AlertQuerySchema()
watchlist_schema = WatchlistSchema()
backtest_run_schema = BacktestRunSchema()


async def validate_query_params(request: Request, schema: Schema) -> dict:
    """
    Validate request query parameters against a Marshmallow schema.
    Returns validated dict or raises HTTPException 400.
    """
    if not HAS_MARSHMALLOW:
        return dict(request.query_params)
    try:
        return schema.load(dict(request.query_params))
    except ValidationError as err:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid query parameters", "details": err.messages},
        )


async def validate_json_body(request: Request, schema: Schema) -> dict:
    """
    Validate request JSON body against a Marshmallow schema.
    Returns validated dict or raises HTTPException 400.
    """
    if not HAS_MARSHMALLOW:
        return await request.json()
    try:
        body = await request.json()
        return schema.load(body or {})
    except ValidationError as err:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid request body", "details": err.messages},
        )


# ---------------------------------------------------------------------------
# JWT Authentication
# ---------------------------------------------------------------------------

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable must be set")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


async def require_jwt_dependency(request: Request) -> dict:
    """
    FastAPI dependency that requires a valid JWT token in the Authorization header.
    Expects: Authorization: Bearer <token>
    Returns the decoded JWT payload.
    """
    if not HAS_JWT:
        return {}

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": "Missing or invalid Authorization header"},
        )

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"error": "Token expired"})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={"error": "Invalid token"})


def generate_jwt(api_key: str) -> str | None:
    """
    Generate a JWT token for the given API key.
    Returns None if the API key is invalid.
    """
    if not HAS_JWT:
        return None

    expected_key = os.environ.get("VIGIL_API_KEY")
    if expected_key and api_key != expected_key:
        return None

    token = jwt.encode(
        {
            "sub": "api_user",
            "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return token


# ---------------------------------------------------------------------------
# Rate Limiting Configuration
# ---------------------------------------------------------------------------

# Default rate limits per endpoint (requests per window)
DEFAULT_RATE_LIMITS: dict[str, str] = {
    "/alerts": "30 per minute",
    "/regime": "10 per minute",
    "/stats": "10 per minute",
    "/trigger": "5 per hour",
    "/backfill": "2 per hour",
    "/evaluate": "5 per hour",
    "/watchlist": "20 per minute",
    "/health": "60 per minute",
    "/metrics": "30 per minute",
}


def get_rate_limits() -> dict[str, str]:
    """
    Return rate limit configuration.
    Can be overridden via environment variable VIGIL_RATE_LIMITS (JSON).
    """
    import json
    custom = os.environ.get("VIGIL_RATE_LIMITS")
    if custom:
        try:
            return json.loads(custom)
        except json.JSONDecodeError:
            pass
    return DEFAULT_RATE_LIMITS


# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------

def get_allowed_origins() -> list[str]:
    """
    Return allowed CORS origins.
    Defaults to http://localhost:3000 for local development.
    WARNING: Using wildcard (*) in production is a security risk.
    """
    origins = os.environ.get("ALLOWED_ORIGINS")
    if origins:
        parsed = [o.strip() for o in origins.split(",")]
        # Security warning if wildcard is explicitly set in production
        if "*" in parsed:
            env = os.environ.get("ENVIRONMENT", "development").lower()
            if env in ("production", "prod"):
                logger.warning(
                    "SECURITY: ALLOWED_ORIGINS contains '*' in production environment. "
                    "This is not safe for production use."
                )
            else:
                logger.warning(
                    "SECURITY: ALLOWED_ORIGINS contains '*'. "
                    "This is not safe for production use."
                )
        return parsed
    # Development default — not production-safe
    logger.warning(
        "SECURITY: ALLOWED_ORIGINS not set. Defaulting to ['http://localhost:3000']. "
        "This default is NOT safe for production use. Set ALLOWED_ORIGINS explicitly."
    )
    return ["http://localhost:3000"]
