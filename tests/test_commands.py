"""Command generation + the drift-guard against the imported unitysvc-py.

The per-service commands are curated but reference real CLI commands and SDK
methods; these tests fail if a rename in unitysvc-py breaks that anchor, and
check the context-filling (only unset secrets, enrollment when required).
"""

from __future__ import annotations

from typing import Any

from unitysvc import AccessPlan, Client

from unitysvc_mcp import commands
from unitysvc_mcp.render import RenderContext


def _plan(**fields: Any) -> AccessPlan:
    base: dict[str, Any] = {
        "enrollment_mode": "disallowed",
        "parameters": [],
        "interfaces": [],
        "channels": [],
    }
    base.update(fields)
    return AccessPlan.from_dict(base)


def _channel(required: list[str]) -> dict[str, Any]:
    return {
        "name": "managed",
        "channel_type": "managed",
        "required_secrets": [{"name": n} for n in required],
        "optional_secrets": [],
    }


# --- drift-guard: the anchors these generators reference must still exist ---


def test_referenced_cli_commands_exist_in_the_typer_app() -> None:
    tree = {path for path, _ in commands.cli_command_tree()}
    for command in ("usvc secrets set", "usvc services enroll", "usvc services dispatch"):
        assert command in tree, f"{command} no longer exists in the unitysvc-py CLI"


def test_referenced_sdk_methods_exist_on_the_client() -> None:
    client = Client(base_url="https://unitysvc.invalid/v1")
    assert callable(client.secrets.set)
    assert callable(client.enrollments.create)
    assert callable(client.services.dispatch)


# --- overviews are generated from the package ------------------------------


def test_cli_overview_lists_real_commands() -> None:
    out = commands.cli_overview()
    assert "usvc services dispatch" in out


def test_sdk_overview_lists_client_resources_with_signatures() -> None:
    out = commands.sdk_overview()
    assert "client.services.dispatch(" in out
    assert "client.secrets" in out


# --- per-service generation fills from context -----------------------------


def test_cli_only_prompts_the_unset_required_secrets() -> None:
    plan = _plan(channels=[_channel(["OPENAI_API_KEY", "ANTHROPIC_API_KEY"])])
    ctx = RenderContext(set_secret_names=frozenset({"ANTHROPIC_API_KEY"}), enrollment_urls=[])

    out = commands.render_cli("svc-1", plan, ctx)

    assert "usvc secrets set OPENAI_API_KEY" in out
    assert "ANTHROPIC_API_KEY" not in out  # already set → not prompted
    assert "usvc services dispatch svc-1" in out
    assert "usvc services enroll" not in out  # disallowed → no enroll step


def test_cli_adds_enroll_when_required() -> None:
    plan = _plan(enrollment_mode="required", channels=[_channel([])])
    ctx = RenderContext(set_secret_names=frozenset(), enrollment_urls=[])

    out = commands.render_cli("svc-1", plan, ctx)

    assert "usvc services enroll svc-1" in out


def test_sdk_snippet_uses_real_method_names() -> None:
    plan = _plan(enrollment_mode="required", channels=[_channel(["OPENAI_API_KEY"])])
    ctx = RenderContext(set_secret_names=frozenset(), enrollment_urls=[])

    out = commands.render_sdk("svc-1", plan, ctx)

    assert 'client.secrets.set("OPENAI_API_KEY"' in out
    assert 'client.enrollments.create(service_id="svc-1")' in out
    assert 'client.services.dispatch("svc-1"' in out


def test_endpoints_uses_the_interface_base_url() -> None:
    plan = _plan(
        interfaces=[{"name": "canonical", "base_url": "https://gw.test/a/svc"}],
        channels=[_channel([])],
    )
    ctx = RenderContext(set_secret_names=frozenset(), enrollment_urls=[])

    out = commands.render_endpoints("svc-1", plan, ctx)

    assert "curl -X POST 'https://gw.test/a/svc'" in out


def test_endpoints_prefers_the_live_enrollment_url() -> None:
    plan = _plan(enrollment_mode="required", channels=[_channel([])])
    ctx = RenderContext(set_secret_names=frozenset(), enrollment_urls=["https://gw.test/e/CODE"])

    out = commands.render_endpoints("svc-1", plan, ctx)

    assert "https://gw.test/e/CODE" in out
