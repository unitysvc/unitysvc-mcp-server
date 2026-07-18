"""Tool availability and transport selection across the two deployments.

The hosted deployment differs from a local one only by having an empty
environment, so these tests assert that property directly: with no keys the
server must advertise the context tools and nothing else.
"""

from __future__ import annotations

import pytest
from mcp.server import MCPServer

from unitysvc_mcp.server import register_tools
from unitysvc_mcp.settings import Settings

MARKET_TOOLS = {"market_list_services"}
SELLER_TOOLS = {"seller_list_services"}


def _settings(**env: str) -> Settings:
    return Settings(_env_file=None, **env)  # type: ignore[arg-type]


def _registered(config: Settings) -> set[str]:
    return set(register_tools(MCPServer("test"), config))


def test_no_keys_registers_market_tools_only() -> None:
    """This is the hosted deployment: an empty environment."""
    config = _settings()

    assert _registered(config) == MARKET_TOOLS
    assert not config.can_act_as_seller
    assert config.mode == "context only (anonymous)"


def test_seller_key_adds_the_seller_tool() -> None:
    config = _settings(UNITYSVC_SELLER_API_KEY="svcpass_sell")

    assert _registered(config) == MARKET_TOOLS | SELLER_TOOLS
    assert config.can_act_as_seller


def test_an_unrecognised_customer_key_changes_nothing() -> None:
    """UNITYSVC_API_KEY unlocks nothing today and must not be silently honoured.

    Customer-side tools are Phase 3 of unitysvc#1492; until they exist a
    customer key would be config that appears to do something and does not.
    """
    config = _settings(
        UNITYSVC_API_KEY="svcpass_cust",
        UNITYSVC_SELLER_API_KEY="svcpass_sell",
    )

    assert _registered(config) == MARKET_TOOLS | SELLER_TOOLS
    assert config.mode == "context + acting as seller"
    assert not hasattr(config, "customer_api_key")


def test_transport_defaults_to_stdio() -> None:
    """The common case is a subprocess of the user's MCP client."""
    assert _settings().transport == "stdio"


def test_transport_opt_in_to_http() -> None:
    assert _settings(UNITYSVC_MCP_TRANSPORT="http").transport == "http"


def test_transport_rejects_unknown_values() -> None:
    with pytest.raises(ValueError):
        _settings(UNITYSVC_MCP_TRANSPORT="carrier-pigeon")


def test_api_urls_use_the_sdk_variable_names() -> None:
    """Matching the SDKs' own names is what makes an existing `usvc` setup
    work with no new values."""
    config = _settings(
        UNITYSVC_API_URL="https://api.example.test/v1",
        UNITYSVC_SELLER_API_URL="https://seller.example.test/v1",
    )

    assert str(config.customer_api_url).startswith("https://api.example.test")
    assert str(config.seller_api_url).startswith("https://seller.example.test")


def test_credentials_are_not_read_from_request_headers() -> None:
    """Credentials come from the environment only.

    A hosted server that accepted a caller's key in a header and forwarded it
    downstream would be the token-passthrough pattern the MCP specification
    forbids. Guarded here because it is a property worth not regressing.
    """
    import inspect

    from unitysvc_mcp import server

    source = inspect.getsource(server)
    assert "ctx.headers" not in source
    assert "Authorization" not in source


def test_tool_names_match_their_module_prefix() -> None:
    """The prefix is the access rule, so it must not drift from the module.

    A `seller_` tool registered by the market module would silently become
    available with no credentials — the exact confusion this layout prevents.
    """
    from mcp.server import MCPServer

    from unitysvc_mcp.tools import market, seller

    for module, prefix in ((market, "market_"), (seller, "seller_")):
        for name in module.register(MCPServer("test")):
            assert name.startswith(prefix), f"{name} is not in the {prefix} module"
