"""Seller command generation + the drift-guard against the imported unitysvc-sellers.

Mirrors ``tests/test_commands.py``: the per-service commands are curated but
reference real CLI commands and SDK methods; these tests fail if a rename in
unitysvc-sellers breaks that anchor.
"""

from __future__ import annotations

from unitysvc_sellers import Client

from unitysvc_mcp import seller_commands
from unitysvc_mcp.seller_context import SellerServiceInfo

# --- drift-guard: the anchors these generators reference must still exist ---


def test_referenced_cli_commands_exist_in_the_typer_app() -> None:
    tree = {path for path, _ in seller_commands.cli_command_tree()}
    for command in (
        "usvc_seller services submit",
        "usvc_seller services update",
        "usvc_seller services run-tests",
        "usvc_seller services show",
    ):
        assert command in tree, f"{command} no longer exists in the unitysvc-sellers CLI"


def test_referenced_sdk_methods_exist_on_the_client() -> None:
    client = Client(api_key="x", base_url="https://x/v1")
    assert callable(client.services.get)
    assert callable(client.services.update)
    assert callable(client.services.submit_for_review)
    assert callable(client.services.run_tests)


# --- overviews are generated from the package -------------------------------


def test_cli_overview_lists_real_commands() -> None:
    out = seller_commands.cli_overview()
    assert "usvc_seller services submit" in out
    assert "usvc_seller services update" in out


def test_sdk_overview_lists_client_resources_with_signatures() -> None:
    out = seller_commands.sdk_overview()
    assert "client.services.submit_for_review(" in out
    assert "client.services.run_tests(" in out
    assert "client.secrets" in out


def test_endpoints_overview_points_at_cli_and_sdk() -> None:
    out = seller_commands.endpoints_overview()
    assert "seller_cli" in out
    assert "seller_sdk" in out


# --- per-service generation fills from context -------------------------------


def test_cli_render_without_info_suggests_submit() -> None:
    out = seller_commands.render_cli("svc-1", None)

    assert "usvc_seller services show svc-1" in out
    assert "usvc_seller services submit svc-1" in out
    assert "usvc_seller services update" not in out


def test_cli_render_draft_status_suggests_submit() -> None:
    info = SellerServiceInfo(id="svc-1", name="svc-1", status="draft")
    out = seller_commands.render_cli("svc-1", info)

    assert "Current status: `draft`" in out
    assert "usvc_seller services submit svc-1" in out


def test_cli_render_active_status_suggests_update_and_run_tests() -> None:
    info = SellerServiceInfo(id="svc-1", name="svc-1", status="active")
    out = seller_commands.render_cli("svc-1", info)

    assert "Current status: `active`" in out
    assert "usvc_seller services update svc-1" in out
    assert "usvc_seller services run-tests svc-1" in out
    assert "usvc_seller services submit svc-1" not in out


def test_sdk_render_draft_status_suggests_submit_for_review() -> None:
    info = SellerServiceInfo(id="svc-1", name="svc-1", status="draft")
    out = seller_commands.render_sdk("svc-1", info)

    assert 'client.services.get("svc-1")' in out
    assert 'client.services.submit_for_review("svc-1")' in out
    assert "client.services.update(" not in out


def test_sdk_render_active_status_suggests_update_and_run_tests() -> None:
    info = SellerServiceInfo(id="svc-1", name="svc-1", status="active")
    out = seller_commands.render_sdk("svc-1", info)

    assert 'client.services.update("svc-1"' in out
    assert 'client.services.run_tests("svc-1")' in out
    assert "submit_for_review" not in out


def test_endpoints_render_includes_status_when_present() -> None:
    info = SellerServiceInfo(id="svc-1", name="svc-1", status="active")
    out = seller_commands.render_endpoints("svc-1", info)

    assert "seller_cli" in out
    assert "Current status: `active`" in out
