from __future__ import annotations

import base64
import json
from typing import Any, Mapping

import httpx

from .models import Principal, Role
from .settings import Settings


def extract_bearer_token(headers: Mapping[str, str] | None) -> str | None:
    """Extract a bearer token from HTTP headers."""

    if not headers:
        return None
    authorization = headers.get("authorization") or headers.get("Authorization")
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization[len(prefix) :].strip() or None


class AuthService:
    """Resolve MCP request authentication into a UnitySVC principal."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client

    async def resolve(self, headers: Mapping[str, str] | None) -> Principal:
        token = extract_bearer_token(headers)
        if not token:
            return Principal()

        if token in self._settings.dev_tokens:
            return self._principal_from_claims(self._settings.dev_tokens[token], token=token)

        if self._settings.auth_introspection_url:
            claims = await self._introspect(token)
            return self._principal_from_claims(claims, token=token)

        # Starter fallback: pass the bearer token through to UnitySVC APIs but do
        # not infer elevated roles. Production should use OAuth introspection or
        # JWT verification and should not grant seller/admin privileges here.
        return Principal(subject="authenticated", roles=["customer"], token=token)

    async def _introspect(self, token: str) -> dict[str, Any]:
        data = {"token": token}
        auth: tuple[str, str] | None = None
        if self._settings.auth_introspection_client_id and self._settings.auth_introspection_client_secret:
            auth = (
                self._settings.auth_introspection_client_id,
                self._settings.auth_introspection_client_secret,
            )
        response = await self._http_client.post(
            str(self._settings.auth_introspection_url),
            data=data,
            auth=auth,
            timeout=10,
        )
        response.raise_for_status()
        claims = response.json()
        if not claims.get("active", True):
            return {"subject": "anonymous", "roles": ["anonymous"]}
        return claims

    def _principal_from_claims(self, claims: dict[str, Any], *, token: str) -> Principal:
        roles = self._extract_roles(claims)
        subject = (
            claims.get("subject")
            or claims.get("sub")
            or claims.get("user_id")
            or claims.get("preferred_username")
            or "authenticated"
        )
        return Principal(
            subject=str(subject),
            roles=roles,
            customer_id=self._first_str(claims, "customer_id", "customerId", "unitysvc_customer_id"),
            seller_id=self._first_str(claims, "seller_id", "sellerId", "unitysvc_seller_id"),
            scopes=self._extract_scopes(claims),
            token=token,
            claims=claims,
        )

    def _extract_roles(self, claims: dict[str, Any]) -> list[Role]:
        raw_roles: set[str] = set()
        for key in ("roles", "role", "unitysvc_roles"):
            value = claims.get(key)
            if isinstance(value, str):
                raw_roles.update(part.strip() for part in value.replace(",", " ").split())
            elif isinstance(value, list):
                raw_roles.update(str(part) for part in value)

        realm_access = claims.get("realm_access")
        if isinstance(realm_access, dict) and isinstance(realm_access.get("roles"), list):
            raw_roles.update(str(part) for part in realm_access["roles"])

        scopes = self._extract_scopes(claims)
        raw_roles.update(scope.removeprefix("role:") for scope in scopes if scope.startswith("role:"))

        allowed = {"customer", "seller", "admin", "support"}
        roles = [role for role in raw_roles if role in allowed]
        return roles or ["customer"]

    def _extract_scopes(self, claims: dict[str, Any]) -> list[str]:
        scope = claims.get("scope") or claims.get("scp")
        if isinstance(scope, str):
            return [part for part in scope.split() if part]
        if isinstance(scope, list):
            return [str(part) for part in scope]
        return []

    def _first_str(self, claims: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = claims.get(key)
            if value is not None:
                return str(value)
        return None


def decode_unverified_jwt_payload(token: str) -> dict[str, Any]:
    """Development helper for inspecting a JWT payload without trusting it."""

    try:
        payload = token.split(".")[1]
    except IndexError:
        return {}
    padded = payload + "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        value = json.loads(decoded)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}
