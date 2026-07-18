from __future__ import annotations

import json
from functools import cached_property
from typing import Any

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the UnitySVC MCP server."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Two backends, one per role deployment. The customer host serves both
    # anonymous catalog reads and authenticated calls since unitysvc#1610, so
    # there is no separate public host to configure.
    customer_api_url: AnyHttpUrl = Field(
        "https://api.unitysvc.com/v1",
        alias="UNITYSVC_CUSTOMER_API_URL",
    )
    seller_api_url: AnyHttpUrl = Field(
        "https://seller.unitysvc.com/v1",
        alias="UNITYSVC_SELLER_API_URL",
    )
    auth_introspection_url: AnyHttpUrl | None = Field(
        None,
        alias="UNITYSVC_AUTH_INTROSPECTION_URL",
    )
    auth_introspection_client_id: str | None = Field(
        None,
        alias="UNITYSVC_AUTH_INTROSPECTION_CLIENT_ID",
    )
    auth_introspection_client_secret: str | None = Field(
        None,
        alias="UNITYSVC_AUTH_INTROSPECTION_CLIENT_SECRET",
    )
    # Loopback by default (matches the SDK default, and keeps its automatic
    # DNS-rebinding protection on). The Docker image overrides host to 0.0.0.0.
    host: str = Field("127.0.0.1", alias="UNITYSVC_MCP_HOST")
    port: int = Field(8000, alias="UNITYSVC_MCP_PORT")
    dev_tokens_json: str = Field("{}", alias="UNITYSVC_MCP_DEV_TOKENS")
    default_catalog_group: str | None = Field(
        None,
        alias="UNITYSVC_DEFAULT_CATALOG_GROUP",
    )

    @cached_property
    def dev_tokens(self) -> dict[str, dict[str, Any]]:
        parsed = json.loads(self.dev_tokens_json or "{}")
        if not isinstance(parsed, dict):
            raise ValueError("UNITYSVC_MCP_DEV_TOKENS must be a JSON object")
        return parsed


settings = Settings()
