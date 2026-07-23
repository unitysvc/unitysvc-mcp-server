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
    if mode == "disallowed":
        rows: list[tuple[str, str]] = []
        for iface in _list(plan.interfaces):
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
            out += _secret_bullets("Secrets to set:", _list(ch.required_secrets), set_names)
            out += _secret_bullets("Optional secrets:", _list(ch.optional_secrets), set_names)

    return "\n".join(out).strip() + "\n"
