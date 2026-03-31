"""
Vigil Security Module

Provides:
- Input validation schemas (Marshmallow)
- JWT authentication decorator
- Rate limiting configuration
- CORS origin management
"""

import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

from flask import jsonify, request

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


# Pre-instantiated schemas
alert_query_schema = AlertQuerySchema()
watchlist_schema = WatchlistSchema()


def validate_query_params(schema: Schema):
    """
    Decorator that validates request query parameters against a Marshmallow schema.
    Returns 400 with error details if validation fails.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not HAS_MARSHMALLOW:
                return f(*args, **kwargs)
            try:
                validated = schema.load(request.args)
                request.validated_args = validated
            except ValidationError as err:
                return jsonify({
                    "error": "Invalid query parameters",
                    "details": err.messages,
                }), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def validate_json_body(schema: Schema):
    """
    Decorator that validates request JSON body against a Marshmallow schema.
    Returns 400 with error details if validation fails.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not HAS_MARSHMALLOW:
                return f(*args, **kwargs)
            try:
                validated = schema.load(request.get_json(silent=True) or {})
                request.validated_json = validated
            except ValidationError as err:
                return jsonify({
                    "error": "Invalid request body",
                    "details": err.messages,
                }), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ---------------------------------------------------------------------------
# JWT Authentication
# ---------------------------------------------------------------------------

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

JWT_SECRET = os.environ.get("JWT_SECRET", os.environ.get("SECRET_KEY", "vigil-dev-fallback"))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def require_jwt(f):
    """
    Decorator that requires a valid JWT token in the Authorization header.
    Expects: Authorization: Bearer <token>
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not HAS_JWT:
            # If PyJWT is not installed, fall back to allowing all requests
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            request.jwt_payload = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated_function


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
    Defaults to wildcard for development; should be restricted in production.
    """
    origins = os.environ.get("ALLOWED_ORIGINS")
    if origins:
        return [o.strip() for o in origins.split(",")]
    # Development default
    return ["*"]
