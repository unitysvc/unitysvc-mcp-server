"""Render a structured ``AccessPlan`` to LLM-facing markdown.

Since unitysvc#1640 the backend serves the "how to use this service" guide as
a generic, context-free :class:`AccessPlan` and renders no prose — rendering is
a client concern. This is the MCP's rendering: the same facts the frontend's
``ServiceUsageGuide`` shows a human, as compact markdown an agent reads.

Generic only: the customer-specific hydration the frontend adds (which secrets
are set, live ``/e/<CODE>`` URLs) needs a customer key and is a follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from unitysvc import AccessPlan, ChannelPlan, SecretRequirement


@dataclass(frozen=True)
class RenderContext:
    """The caller's own context for one service (customer_* tools).

    ``set_secret_names`` are the names of secrets the caller has already set;
    ``enrollment_urls`` are their live ``/e/<CODE>`` URLs for this service.
    """

    set_secret_names: frozenset[str]
    enrollment_urls: list[str]


# Generated attrs models leave unset optionals as an ``UNSET`` sentinel rather
# than None, so coerce by type instead of truthiness-on-a-sentinel.


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _dict(value: Any) -> dict[str, Any]:
    """Coerce a routing-key value to a plain dict.

    Generated open-dict fields (``additionalProperties``) come back as a model,
    not a ``dict`` — its ``to_dict()`` yields the underlying mapping.
    """
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        return result if isinstance(result, dict) else {}
    return {}


_ENROLLMENT_POSTURE = {
    "required": "Enrollment required — enroll once, then use any channel.",
    "optional": "Enrollment optional — some channels need it, others you can use directly.",
}
_ENDPOINT_HINT = {
    "required": "Enroll to receive your endpoint, then call your per-enrollment `/e/<CODE>` URL.",
    "optional": "Enrolled channels are reached at your per-enrollment `/e/<CODE>` URL.",
}


def _price(ch: ChannelPlan) -> str:
    """Display price, in priority order (mirrors the frontend)."""
    described = _str(ch.price_description)
    if described:
        return described
    if ch.free is True:
        return "Free"
    amount = _str(ch.price)
    if amount:
        return f"{amount} {_str(ch.currency) or 'USD'}"
    return "Paid"


def _verb(ch: ChannelPlan, mode: str) -> str | None:
    """One-line "what this channel needs" — suppressed under a whole-service gate."""
    channel_type = _str(ch.channel_type)
    if channel_type == "byok":
        return "Bring your own key."
    if channel_type == "byoe":
        return "Bring your own endpoint."
    under_gate = mode == "required"
    if ch.requires_enrollment is True and not under_gate:
        return "Enroll to access."
    if not under_gate and not _list(ch.required_secrets):
        return "Use it directly."
    return None


def _channel_field(ch: ChannelPlan, name: str) -> Any:
    """A ChannelPlan field by name, tolerating an older generated model.

    Fields the installed SDK's generated model doesn't know yet (its models lag
    the backend schema) arrive in ``additional_properties`` — read the typed
    attribute first, then fall back there.
    """
    value = getattr(ch, name, None)
    if value is not None:
        return value
    extra = getattr(ch, "additional_properties", None)
    return extra.get(name) if isinstance(extra, dict) else None


def _applicable_interface_names(ch: ChannelPlan) -> list[str] | None:
    """The channel's declared ``applicable_interfaces`` (unitysvc#1825), or None.

    Instruction-only channel↔interface pairing; ``None`` means undeclared, in
    which case every shared interface stays applicable.
    """
    raw = _channel_field(ch, "applicable_interfaces")
    if not isinstance(raw, list):
        return None
    names = [n for n in raw if isinstance(n, str) and n]
    return names or None


def _channel_call_lines(
    ch: ChannelPlan, interfaces: list[Any], mode: str, multi: bool
) -> list[str]:
    """Per-channel "Call at" lines for a direct channel (unitysvc#1825).

    Composed from the channel's applicable interfaces (declared, or every
    shared interface when undeclared), with the ``@<channel>`` pin appended.
    Suppressed for the lone-channel/undeclared case — the Endpoint section
    already says it — and for enrollable channels, whose URL is per-enrollment.
    """
    if ch.requires_enrollment is True or mode == "required":
        return []
    names = _applicable_interface_names(ch)
    if names is None and not multi:
        return []
    pool = [i for i in interfaces if _str(getattr(i, "base_url", None))]
    if names is not None:
        pool = [i for i in pool if _str(getattr(i, "name", None)) in names]
    if not pool:
        return []
    sel = _str(_channel_field(ch, "selector")) or ""
    note = f" (the `{sel}` suffix pins this channel)" if sel else ""
    return [f"- Call at: `{_str(i.base_url)}{sel}`{note}" for i in pool]


def _secret_bullets(
    label: str,
    secrets: list[SecretRequirement],
    set_names: frozenset[str] | None = None,
) -> list[str]:
    if not secrets:
        return []
    lines = [label]
    for secret in secrets:
        name = _str(secret.name) or ""
        text = f"- `{name}`"
        if set_names is not None:
            text += " (set)" if name in set_names else " (not set)"
        description = _str(secret.description)
        if description:
            text += f" — {description}"
        default = _str(getattr(secret, "default", None))
        if default:
            text += f" (defaults to `{default}`)"
        lines.append(text)
    return lines


def render_access_plan(plan: AccessPlan, *, context: RenderContext | None = None) -> str:
    """Render an :class:`AccessPlan` to markdown for an agent to read.

    With ``context`` (a ``customer_*`` call), secrets are marked (set)/(not set)
    and the caller's live ``/e/<CODE>`` URLs replace the generic enroll hint.
    """
    mode = plan.enrollment_mode if isinstance(plan.enrollment_mode, str) else "disallowed"
    set_names = context.set_secret_names if context is not None else None
    channels = _list(plan.channels)
    out: list[str] = ["# How to use this service"]

    # Enrollment — only when the service needs it.
    if mode != "disallowed":
        out += ["", "## Enrollment", _ENROLLMENT_POSTURE.get(mode, "")]
        parameters = _list(plan.parameters)
        if parameters:
            out += ["", "Enroll with:"]
            for param in parameters:
                name = _str(param.name) or ""
                required = "required" if param.required is True else "optional"
                line = f"- `{name}` ({required})"
                description = _str(param.description)
                if description:
                    line += f" — {description}"
                out.append(line)

    # Endpoint — how to actually call it.
    out += ["", "## Endpoint"]
    plan_interfaces = _list(plan.interfaces)
    if mode == "disallowed":
        urled = [i for i in plan_interfaces if _str(getattr(i, "base_url", None))]
        if len(urled) > 1:
            # Several shared interfaces (e.g. bedrock's OpenAI-style
            # provider_api vs native-runtime converse_api): name each one, and
            # let each channel below say which it uses (unitysvc#1825).
            out.append(
                "This service has several interfaces — each channel below lists the one(s) it uses:"
            )
            for iface in urled:
                name = _str(getattr(iface, "name", None))
                url = _str(iface.base_url)
                line = f"- `{name}`: `{url}`" if name else f"- `{url}`"
                routing = ", ".join(
                    f"`{str(k).upper()}` = `{v}`" for k, v in _dict(iface.routing_key).items()
                )
                if routing:
                    line += f" ({routing})"
                out.append(line)
        else:
            rows: list[tuple[str, str]] = []
            for iface in plan_interfaces:
                base_url = _str(iface.base_url)
                if base_url:
                    rows.append(("SERVICE_BASE_URL", base_url))
                rows += [(str(k).upper(), str(v)) for k, v in _dict(iface.routing_key).items()]
            if rows:
                out.append("Call the service at:")
                out += [f"- `{key}` = `{value}`" for key, value in rows]
            else:
                out.append("Call the service at its gateway interface.")
    elif context is not None and context.enrollment_urls:
        out.append("Your endpoint URL(s):")
        out += [f"- {url}" for url in context.enrollment_urls]
    else:
        out.append(_ENDPOINT_HINT.get(mode, ""))

    # Channels / pricing.
    if channels:
        multi = len(channels) > 1
        out += ["", "## Channels" if multi else "## Pricing"]
        for ch in channels:
            if multi:
                out += ["", f"### {_str(ch.name) or ''}"]
            verb = _verb(ch, mode)
            out.append(f"{_price(ch)}." + (f" {verb}" if verb else ""))
            # Secrets and enrollment are separate prerequisites (unitysvc#1813):
            # enrolling never collects secrets, so a channel needing both must
            # say so or "Enroll" reads like the whole story.
            enrolls = ch.requires_enrollment is True or mode == "required"
            if enrolls and _list(ch.required_secrets):
                out.append(
                    "Two separate steps are required: set the secrets below "
                    "AND enroll — enrolling alone is not enough."
                )
            out += _secret_bullets("Secrets to set:", _list(ch.required_secrets), set_names)
            out += _secret_bullets("Optional secrets:", _list(ch.optional_secrets), set_names)
            out += _channel_call_lines(ch, plan_interfaces, mode, multi)

    return "\n".join(out).strip() + "\n"
