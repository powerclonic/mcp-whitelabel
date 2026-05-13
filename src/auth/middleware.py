"""OIDC JWT validation middleware.

Validates Bearer tokens against the configured OIDC issuer using the
issuer's JWKS endpoint.  The JWKS document is cached for
``jwks_cache_ttl_seconds`` to avoid per-request network calls.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from jose import JWTError, jwt

from src.config.settings import settings


class AuthError(Exception):
    """Raised when a token cannot be validated."""


class JWKSCache:
    """Thread-friendly, TTL-based cache for JWKS documents."""

    def __init__(self, ttl: int | None = None) -> None:
        self._ttl = ttl if ttl is not None else settings.jwks_cache_ttl_seconds
        self._keys: list[dict[str, Any]] = []
        self._fetched_at: float = 0.0

    def _is_expired(self) -> bool:
        return (time.monotonic() - self._fetched_at) >= self._ttl

    def get_keys(self, issuer: str | None = None) -> list[dict[str, Any]]:
        if self._is_expired():
            self._refresh(issuer or settings.oidc_issuer)
        return self._keys

    def _refresh(self, issuer: str) -> None:
        jwks_uri = issuer.rstrip("/") + "/.well-known/jwks.json"
        try:
            response = httpx.get(jwks_uri, timeout=10.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AuthError(f"Failed to fetch JWKS from {jwks_uri}: {exc}") from exc
        self._keys = response.json().get("keys", [])
        self._fetched_at = time.monotonic()


# Module-level cache shared across requests.
_jwks_cache = JWKSCache()


def validate_token(
    token: str,
    issuer: str | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    """Validate a JWT and return its decoded claims.

    Args:
        token: Raw Bearer token (without the "Bearer " prefix).
        issuer: Override the configured OIDC issuer.
        audience: Override the configured audience.

    Returns:
        Decoded JWT claims dict.

    Raises:
        AuthError: If the token is invalid or cannot be verified.
    """
    _issuer = issuer or settings.oidc_issuer
    _audience = audience or settings.oidc_audience

    keys = _jwks_cache.get_keys(_issuer)
    if not keys:
        raise AuthError("No JWKS keys available — cannot validate token")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            keys,
            algorithms=["RS256"],
            audience=_audience,
            issuer=_issuer,
            options={"verify_exp": True},
        )
    except JWTError as exc:
        raise AuthError(f"Token validation failed: {exc}") from exc

    return claims


def extract_bearer_token(authorization: str) -> str:
    """Extract the raw token from an 'Authorization: Bearer <token>' header."""
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Authorization header must be 'Bearer <token>'")
    return parts[1]
