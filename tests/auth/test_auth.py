"""Tests for OIDC JWT middleware and RBAC scope enforcement."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from src.auth.middleware import (
    AuthError,
    JWKSCache,
    extract_bearer_token,
    validate_token,
)
from src.auth.rbac import check_scope, get_scopes, require_scope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )


# ---------------------------------------------------------------------------
# JWKSCache tests
# ---------------------------------------------------------------------------

class TestJWKSCache:
    def test_expired_on_init(self) -> None:
        cache = JWKSCache(ttl=3600)
        assert cache._is_expired()

    def test_refresh_fetches_keys(self) -> None:
        fake_keys = [{"kty": "RSA", "kid": "1"}]
        with patch("src.auth.middleware.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"keys": fake_keys}
            mock_get.return_value = mock_resp
            cache = JWKSCache(ttl=3600)
            keys = cache.get_keys("https://issuer.example")
        assert keys == fake_keys

    def test_refresh_raises_on_http_error(self) -> None:
        import httpx
        with patch("src.auth.middleware.httpx.get", side_effect=httpx.HTTPError("err")):
            cache = JWKSCache(ttl=3600)
            with pytest.raises(AuthError, match="Failed to fetch JWKS"):
                cache.get_keys("https://issuer.example")

    def test_cache_not_expired_within_ttl(self) -> None:
        cache = JWKSCache(ttl=3600)
        cache._fetched_at = 1e30  # far future
        assert not cache._is_expired()

    def test_empty_keys_raises_auth_error(self) -> None:
        with patch("src.auth.middleware.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"keys": []}
            mock_get.return_value = mock_resp
            with pytest.raises(AuthError, match="No JWKS keys"):
                validate_token("tok", issuer="https://issuer.example", audience="aud")


# ---------------------------------------------------------------------------
# validate_token tests
# ---------------------------------------------------------------------------

class TestValidateToken:
    def test_invalid_token_raises(self) -> None:
        fake_keys = [{"kty": "RSA", "kid": "1"}]
        with patch("src.auth.middleware._jwks_cache.get_keys", return_value=fake_keys):
            with pytest.raises(AuthError, match="Token validation failed"):
                validate_token("not.a.jwt", issuer="https://i.example", audience="aud")

    def test_valid_token_returns_claims(self) -> None:
        from cryptography.hazmat.primitives import serialization
        from jose import jwk as jose_jwk

        private_key = _make_rsa_key()
        public_key = private_key.public_key()
        pem = public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        jwk_dict = jose_jwk.construct(pem, algorithm="RS256").to_dict()

        payload = {
            "sub": "user1",
            "iss": "https://issuer.example",
            "aud": "mcp-governance",
            "scope": "query:read compliance:read",
        }
        private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        token = jwt.encode(payload, private_pem, algorithm="RS256")

        with patch("src.auth.middleware._jwks_cache.get_keys", return_value=[jwk_dict]):
            claims = validate_token(
                token,
                issuer="https://issuer.example",
                audience="mcp-governance",
            )
        assert claims["sub"] == "user1"


# ---------------------------------------------------------------------------
# extract_bearer_token tests
# ---------------------------------------------------------------------------

class TestExtractBearerToken:
    def test_valid_header(self) -> None:
        token = extract_bearer_token("Bearer abc123")
        assert token == "abc123"

    def test_missing_bearer_prefix_raises(self) -> None:
        with pytest.raises(AuthError, match="must be 'Bearer"):
            extract_bearer_token("abc123")

    def test_extra_parts_raises(self) -> None:
        with pytest.raises(AuthError):
            extract_bearer_token("Bearer abc extra")

    def test_case_insensitive_bearer(self) -> None:
        token = extract_bearer_token("bearer mytoken")
        assert token == "mytoken"


# ---------------------------------------------------------------------------
# get_scopes / check_scope tests
# ---------------------------------------------------------------------------

class TestGetScopes:
    def test_scope_string(self) -> None:
        scopes = get_scopes({"scope": "query:read compliance:read"})
        assert "query:read" in scopes
        assert "compliance:read" in scopes

    def test_scp_list(self) -> None:
        scopes = get_scopes({"scp": ["query:read", "compliance:read"]})
        assert "compliance:read" in scopes

    def test_empty_claims(self) -> None:
        assert get_scopes({}) == set()

    def test_both_fields_merged(self) -> None:
        scopes = get_scopes({"scope": "a:read", "scp": ["b:write"]})
        assert "a:read" in scopes
        assert "b:write" in scopes


class TestCheckScope:
    def test_present_scope_passes(self) -> None:
        check_scope({"scope": "compliance:read"}, "compliance:read")  # no exception

    def test_missing_scope_raises(self) -> None:
        with pytest.raises(AuthError, match="Insufficient scope"):
            check_scope({"scope": "query:read"}, "compliance:read")


# ---------------------------------------------------------------------------
# require_scope decorator tests
# ---------------------------------------------------------------------------

class TestRequireScope:
    def test_passes_with_correct_scope(self) -> None:
        @require_scope("compliance:read")
        def my_tool(x: int, claims: dict) -> int:
            return x * 2

        result = my_tool(5, claims={"scope": "compliance:read"})
        assert result == 10

    def test_raises_with_missing_scope(self) -> None:
        @require_scope("compliance:read")
        def my_tool(x: int, claims: dict) -> int:
            return x * 2

        with pytest.raises(AuthError, match="Insufficient scope"):
            my_tool(5, claims={"scope": "query:read"})

    def test_raises_without_claims(self) -> None:
        @require_scope("compliance:read")
        def my_tool(x: int) -> int:
            return x * 2

        with pytest.raises(AuthError, match="No claims"):
            my_tool(5)

    def test_positional_claims(self) -> None:
        @require_scope("query:read")
        def my_tool(query: str, claims: dict) -> str:
            return query.upper()

        result = my_tool("hello", {"scope": "query:read"})
        assert result == "HELLO"
