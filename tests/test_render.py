"""Rendering the structured AccessPlan to LLM markdown (#1638).

Plans are built with ``AccessPlan.from_dict`` (the real parse path), then
rendered; assertions check the facts an agent needs, mirroring the frontend's
ServiceUsageGuide.
"""

from __future__ import annotations

from typing import Any

from unitysvc import AccessPlan

from unitysvc_mcp.render import render_access_plan


def _plan(**fields: Any) -> AccessPlan:
    base: dict[str, Any] = {
        "enrollment_mode": "disallowed",
        "parameters": [],
        "interfaces": [],
        "channels": [],
    }
    base.update(fields)
    return AccessPlan.from_dict(base)


def _channel(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "managed",
        "channel_type": "managed",
        "requires_enrollment": False,
        "required_secrets": [],
        "optional_secrets": [],
    }
    base.update(fields)
    return base


def test_disallowed_renders_endpoint_rows_and_direct_verb() -> None:
    md = render_access_plan(
        _plan(
            interfaces=[
                {"name": "canonical", "base_url": "https://gw/a/x", "routing_key": {"model": "m1"}}
            ],
            channels=[_channel(price_description="$0.01/call")],
        )
    )
    assert md.startswith("# How to use this service")
    assert "## Endpoint" in md
    assert "`SERVICE_BASE_URL` = `https://gw/a/x`" in md
    assert "`MODEL` = `m1`" in md
    assert "## Pricing" in md
    assert "$0.01/call. Use it directly." in md
    assert "## Enrollment" not in md  # disallowed → no enrollment section


def test_optional_enrollment_section_and_per_enrollment_endpoint() -> None:
    md = render_access_plan(
        _plan(
            enrollment_mode="optional",
            parameters=[{"name": "region", "required": True, "description": "Deploy region"}],
            channels=[
                _channel(name="direct", free=True),
                _channel(
                    name="enrolled",
                    channel_type="enrollable",
                    price="1.5",
                    currency="USD",
                    requires_enrollment=True,
                ),
            ],
        )
    )
    assert "## Enrollment" in md
    assert "Enrollment optional" in md
    assert "- `region` (required) — Deploy region" in md
    assert "/e/<CODE>" in md  # per-enrollment endpoint, not a shared base_url
    assert "## Channels" in md  # multiple channels → titled
    assert "### enrolled" in md
    assert "1.5 USD. Enroll to access." in md


def test_required_suppresses_the_per_channel_verb() -> None:
    md = render_access_plan(
        _plan(
            enrollment_mode="required",
            channels=[_channel(free=True, requires_enrollment=True)],
        )
    )
    assert "Enrollment required" in md
    assert "Enroll to receive your endpoint" in md
    assert "Free." in md
    # Stated once in Enrollment; not repeated per channel under a whole-service gate.
    assert "Enroll to access." not in md
    assert "Use it directly." not in md


def test_price_priority_numeric_and_paid_fallback() -> None:
    numeric = render_access_plan(_plan(channels=[_channel(price="2", currency="EUR")]))
    assert "2 EUR." in numeric

    paid = render_access_plan(_plan(channels=[_channel()]))  # no description, not free, no amount
    assert "Paid." in paid


def test_byok_and_byoe_verbs() -> None:
    md = render_access_plan(
        _plan(
            channels=[
                _channel(name="k", channel_type="byok"),
                _channel(name="e", channel_type="byoe"),
            ]
        )
    )
    assert "Bring your own key." in md
    assert "Bring your own endpoint." in md


def test_required_and_optional_secrets_with_default() -> None:
    md = render_access_plan(
        _plan(
            channels=[
                _channel(
                    free=True,
                    required_secrets=[{"name": "OPENAI_API_KEY", "description": "your key"}],
                    optional_secrets=[{"name": "ORG", "description": "org id", "default": "acme"}],
                )
            ]
        )
    )
    assert "Secrets to set:" in md
    assert "- `OPENAI_API_KEY` — your key" in md
    assert "Optional secrets:" in md
    assert "- `ORG` — org id (defaults to `acme`)" in md
