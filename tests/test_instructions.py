"""The platform primer injected into the server's ``instructions``.

The primer is what grounds a session before any tool call, so these guard the
two properties that matter: it is actually wired onto the server, and it maps
the tools while telling the model not to answer from training data.
"""

from __future__ import annotations

from unitysvc_mcp.instructions import PRIMER


def test_server_injects_the_primer() -> None:
    from unitysvc_mcp.server import mcp

    assert mcp.instructions == PRIMER


def test_primer_maps_the_tools_and_forbids_guessing() -> None:
    # Names the docs tools the model must defer platform questions to,
    assert "docs_list_topics" in PRIMER
    assert "docs_get_topic" in PRIMER
    # the other credential-gated tiers,
    assert "market_list_services" in PRIMER
    assert "customer_" in PRIMER
    assert "seller_" in PRIMER
    # forbids answering from prior knowledge,
    assert "training data" in PRIMER
    # and explains the cross-reference format so the model follows topic links.
    assert "?topic=" in PRIMER


def test_primer_frames_platform_customer_and_seller_accurately() -> None:
    # Multi-protocol gateway, not just LLM/API,
    assert "multi-protocol" in PRIMER
    assert "s3" in PRIMER and "smtp" in PRIMER
    # customer access has three shapes: direct, secrets, enrollment,
    assert "directly" in PRIMER
    assert "customer secrets" in PRIMER
    assert "enrollment" in PRIMER
    # and the seller value prop: bring an endpoint, platform does market/billing.
    assert "bring an endpoint" in PRIMER
    assert "billing" in PRIMER
    # tooling named correctly per role: customer unitysvc-py/usvc,
    assert "unitysvc-py" in PRIMER
    # seller unitysvc-sellers/usvc_seller (not the customer `usvc`).
    assert "unitysvc-sellers" in PRIMER
    assert "usvc_seller" in PRIMER
    # a gateway call is the mechanism, not the only way to consume a service,
    assert "curl" in PRIMER
    assert "third-party" in PRIMER
    # the key rides any of three auth headers, not Bearer only,
    assert "x-api-key" in PRIMER
    assert "x-goog-api-key" in PRIMER
    # and calls can be deferred/scheduled, not only immediate.
    assert "delay" in PRIMER
    assert "schedule" in PRIMER
