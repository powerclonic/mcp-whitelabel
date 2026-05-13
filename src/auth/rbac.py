"""RBAC scope enforcement for MCP tools.

Each MCP tool declares the scope it requires.  The ``require_scope``
decorator checks that the decoded JWT claims contain the required scope
before the tool executes.
"""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from src.auth.middleware import AuthError


def get_scopes(claims: dict[str, Any]) -> set[str]:
    """Extract OAuth 2.0 scopes from JWT claims.

    Supports both space-delimited ``scope`` string and ``scp`` list,
    as used by different IdP implementations.
    """
    scopes: set[str] = set()

    scope_str = claims.get("scope", "")
    if isinstance(scope_str, str):
        scopes.update(scope_str.split())

    scp_list = claims.get("scp", [])
    if isinstance(scp_list, list):
        scopes.update(scp_list)

    return scopes


def check_scope(claims: dict[str, Any], required: str) -> None:
    """Raise AuthError if *required* scope is absent from *claims*.

    Args:
        claims: Decoded JWT payload.
        required: Single scope string that must be present.

    Raises:
        AuthError: If the required scope is not found.
    """
    if required not in get_scopes(claims):
        raise AuthError(f"Insufficient scope: '{required}' required")


F = Callable[..., Any]


def require_scope(scope: str) -> Callable[[F], F]:
    """Decorator factory that enforces a required JWT scope.

    The decorated function must accept ``claims: dict[str, Any]`` as a
    keyword argument (or positional argument).  Callers are responsible
    for providing the decoded claims.

    Example::

        @require_scope("compliance:read")
        def check_library_compliance(name, version, claims):
            ...
    """
    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            claims: dict[str, Any] | None = kwargs.get("claims")
            if claims is None:
                # Try to find claims in positional args by inspecting annotations
                import inspect
                sig = inspect.signature(fn)
                params = list(sig.parameters.keys())
                for i, param_name in enumerate(params):
                    if param_name == "claims" and i < len(args):
                        claims = args[i]
                        break
            if claims is None:
                raise AuthError("No claims provided — cannot enforce scope")
            check_scope(claims, scope)
            return fn(*args, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorator
