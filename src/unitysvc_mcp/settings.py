from __future__ import annotations

from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the UnitySVC MCP server.

    Credentials come from the process environment and nowhere else — no
    request headers, no config file, no token exchange. That is what the MCP
    specification prescribes for stdio servers ("retrieve credentials from
    the environment"), and it is what keeps the hosted deployment honest: it
    runs with an empty environment, so it has no credential to hold, log, or
    leak, rather than holding one it promises not to use.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Credentials -------------------------------------------------------
    # Presence is the only role signal. `svcpass_` keys already encode
    # `role_type`, and the backend authorises every call from the key, so the
    # server never infers a role of its own.
    customer_api_key: str | None = Field(None, alias="UNITYSVC_API_KEY")
    seller_api_key: str | None = Field(None, alias="UNITYSVC_SELLER_API_KEY")

    # --- Backends ----------------------------------------------------------
    # Names match the SDKs' own, so anyone already set up for the `usvc` CLI
    # supplies no new values. The customer host serves both anonymous catalog
    # reads and authenticated calls since unitysvc#1610, so there is no
    # separate public host.
    customer_api_url: AnyHttpUrl = Field(
        "https://api.unitysvc.com/v1",
        alias="UNITYSVC_API_URL",
    )
    seller_api_url: AnyHttpUrl = Field(
        "https://seller.unitysvc.com/v1",
        alias="UNITYSVC_SELLER_API_URL",
    )

    # --- Transport ---------------------------------------------------------
    # stdio by default: the common case is a user's own MCP client spawning
    # this as a subprocess. `http` is for the hosted deployment.
    transport: Literal["stdio", "http"] = Field(
        "stdio",
        alias="UNITYSVC_MCP_TRANSPORT",
    )
    # HTTP only. Loopback by default (matches the SDK default and keeps its
    # automatic DNS-rebinding protection on); the Docker image sets 0.0.0.0.
    host: str = Field("127.0.0.1", alias="UNITYSVC_MCP_HOST")
    port: int = Field(8000, alias="UNITYSVC_MCP_PORT")

    default_catalog_group: str | None = Field(
        None,
        alias="UNITYSVC_DEFAULT_CATALOG_GROUP",
    )

    @property
    def can_act_as_customer(self) -> bool:
        """Whether authenticated customer operations are available."""
        return bool(self.customer_api_key)

    @property
    def can_act_as_seller(self) -> bool:
        """Whether seller operations are available."""
        return bool(self.seller_api_key)

    @property
    def mode(self) -> str:
        """Human-readable summary of what this process can do, for logging."""
        acting = [
            name
            for name, enabled in (
                ("customer", self.can_act_as_customer),
                ("seller", self.can_act_as_seller),
            )
            if enabled
        ]
        return f"context + acting as {'/'.join(acting)}" if acting else "context only (anonymous)"


settings = Settings()
