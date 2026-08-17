"""Rendering the structured AccessPlan to LLM markdown (#1638).

Plans are built with ``AccessPlan.from_dict`` (the real parse path), then
rendered; assertions check the facts an agent needs, mirroring the frontend's
ServiceUsageGuide.
"""

from __future__ import annotations

from typing import Any

from unitysvc import AccessPlan

from unitysvc_mcp.render import RenderContext, render_access_plan


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
    assert '- include `"model": "m1"` in the request body' in md
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


def test_context_marks_secrets_set_and_not_set() -> None:
    plan = _plan(
        channels=[
            _channel(
                free=True,
                required_secrets=[
                    {"name": "OPENAI_API_KEY", "description": "your key"},
                    {"name": "ANTHROPIC_API_KEY"},
                ],
            )
        ]
    )
    ctx = RenderContext(set_secret_names=frozenset({"OPENAI_API_KEY"}), enrollment_urls=[])
    md = render_access_plan(plan, context=ctx)

    assert "- `OPENAI_API_KEY` (set) — your key" in md
    assert "- `ANTHROPIC_API_KEY` (not set)" in md


def test_context_shows_live_enrollment_urls_instead_of_hint() -> None:
    plan = _plan(
        enrollment_mode="required",
        channels=[_channel(free=True, requires_enrollment=True)],
    )
    ctx = RenderContext(
        set_secret_names=frozenset(),
        enrollment_urls=["https://gw.test/e/CODE123"],
    )
    md = render_access_plan(plan, context=ctx)

    assert "Your endpoint URL(s):" in md
    assert "- https://gw.test/e/CODE123" in md
    assert "Enroll to receive your endpoint" not in md  # generic hint replaced


def test_context_without_enrollment_urls_keeps_the_generic_hint() -> None:
    plan = _plan(enrollment_mode="required", channels=[_channel(free=True)])
    ctx = RenderContext(set_secret_names=frozenset(), enrollment_urls=[])
    md = render_access_plan(plan, context=ctx)

    assert "Enroll to receive your endpoint" in md


def test_multi_interface_channels_pair_via_applicable_interfaces() -> None:
    """unitysvc#1825: a bedrock-shaped plan — two shared interfaces, each
    channel declaring the one it is reached through. The declaration arrives
    via ``from_dict`` (additional_properties until the SDK regenerates)."""
    gw = "https://api.staging.svcpass.com"
    md = render_access_plan(
        _plan(
            interfaces=[
                {"name": "converse_api", "base_url": f"{gw}/bedrock-runtime/model/voxtral"},
                {
                    "name": "provider_api",
                    "base_url": f"{gw}/bedrock",
                    "routing_key": {"model": "voxtral"},
                },
            ],
            channels=[
                _channel(
                    name="byok",
                    channel_type="byok",
                    applicable_interfaces=["provider_api"],
                ),
                _channel(
                    name="converse",
                    channel_type="byok",
                    selector="@converse",
                    applicable_interfaces=["converse_api"],
                ),
            ],
        )
    )
    # The endpoint section names both interfaces instead of two bare
    # SERVICE_BASE_URL rows.
    assert "several interfaces" in md
    assert (
        f'- `provider_api`: `{gw}/bedrock` (include `"model": "voxtral"` in the request body)' in md
    )
    assert f"- `converse_api`: `{gw}/bedrock-runtime/model/voxtral`" in md
    # Each channel calls its own interface, converse pinned via @converse.
    assert f"- Call at: `{gw}/bedrock`" in md
    assert f"- Call at: `{gw}/bedrock-runtime/model/voxtral@converse`" in md
    # The wrong pairings must not appear.
    assert f"- Call at: `{gw}/bedrock-runtime/model/voxtral`\n" not in md
    assert f"- Call at: `{gw}/bedrock@converse`" not in md


def test_undeclared_channels_list_every_interface() -> None:
    """Without applicable_interfaces every shared interface stays applicable."""
    md = render_access_plan(
        _plan(
            interfaces=[
                {"name": "a", "base_url": "https://gw/one"},
                {"name": "b", "base_url": "https://gw/two"},
            ],
            channels=[
                _channel(name="x", channel_type="managed"),
                _channel(name="y", channel_type="byok", selector="@y"),
            ],
        )
    )
    assert "- Call at: `https://gw/one`" in md
    assert "- Call at: `https://gw/two`" in md
    assert "- Call at: `https://gw/one@y`" in md
    assert "- Call at: `https://gw/two@y`" in md


def test_secrets_plus_enrollment_calls_out_both_steps() -> None:
    """unitysvc#1813 separation: enrolling never collects secrets, so a channel
    needing both must say both are required."""
    md = render_access_plan(
        _plan(
            enrollment_mode="required",
            channels=[
                _channel(
                    name="plus",
                    channel_type="enrollable",
                    requires_enrollment=True,
                    required_secrets=[{"name": "RELAY_PASSWORD"}],
                )
            ],
        )
    )
    assert "Two separate steps are required" in md
    assert "enrolling alone is not enough" in md


def test_enrollment_without_secrets_stays_quiet() -> None:
    md = render_access_plan(
        _plan(
            enrollment_mode="required",
            channels=[_channel(name="plus", channel_type="enrollable", requires_enrollment=True)],
        )
    )
    assert "Two separate steps" not in md


def test_channel_request_formats_render_with_topic_pointer() -> None:
    """unitysvc#1828: formats render as a named line pointing at the docs
    topic (readable via docs_get_topic), and format-disjoint channels drop
    the @pin — routing is automatic."""
    gw = "https://api.test"
    md = render_access_plan(
        _plan(
            interfaces=[
                {"name": "provider_api", "base_url": f"{gw}/bedrock"},
                {"name": "converse_api", "base_url": f"{gw}/bedrock-runtime/model/x"},
            ],
            channels=[
                _channel(
                    name="byok",
                    channel_type="byok",
                    request_formats=["openai", "anthropic"],
                    applicable_interfaces=["provider_api"],
                ),
                _channel(
                    name="converse",
                    channel_type="byok",
                    selector="@converse",
                    request_formats=["bedrock_converse", "bedrock_invoke"],
                    applicable_interfaces=["converse_api"],
                ),
            ],
        )
    )
    assert "Request format: OpenAI Chat Completions (docs topic: `openai-format`)" in md
    assert "AWS Bedrock Converse (docs topic: `converse-format`)" in md
    # Disjoint formats on both sides -> the pin is redundant and dropped.
    assert "routed here automatically" in md
    assert "@converse" not in md


def test_pin_stays_when_a_sibling_serves_everything() -> None:
    gw = "https://api.test"
    md = render_access_plan(
        _plan(
            interfaces=[
                {"name": "provider_api", "base_url": f"{gw}/bedrock"},
                {"name": "converse_api", "base_url": f"{gw}/bedrock-runtime/model/x"},
            ],
            channels=[
                _channel(name="byok", channel_type="byok", applicable_interfaces=["provider_api"]),
                _channel(
                    name="converse",
                    channel_type="byok",
                    selector="@converse",
                    request_formats=["bedrock_converse"],
                    applicable_interfaces=["converse_api"],
                ),
            ],
        )
    )
    # byok declares nothing -> it overlaps everything -> the pin stays,
    # embedded in the copyable URL, never explained.
    assert f"- Call at: `{gw}/bedrock-runtime/model/x@converse`" in md
    assert "pins this channel" not in md


def test_service_level_input_formats_are_the_fallback() -> None:
    """The msg-to-* fleet declares its format on the offering
    (details.input_formats), not per channel — the plan-level field feeds the
    same format line."""
    md = render_access_plan(
        _plan(
            input_formats=["msg"],
            interfaces=[{"name": "canonical", "base_url": "https://gw/labs/msg-to-twilio-sms"}],
            channels=[_channel(name="gateway", free=True)],
        )
    )
    assert "Request format: Msg envelope (docs topic: `msg-format`)" in md


def test_unknown_format_renders_as_raw_code() -> None:
    md = render_access_plan(
        _plan(
            interfaces=[{"name": "canonical", "base_url": "https://gw/x"}],
            channels=[_channel(name="a", request_formats=["x-acme"])],
        )
    )
    assert "Request format: `x-acme`" in md
