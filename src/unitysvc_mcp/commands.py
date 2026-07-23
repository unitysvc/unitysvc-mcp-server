"""Generate how-to-use output for a service, across three modalities.

Command *shapes* are anchored to the in-process ``unitysvc-py`` — the CLI tree
is introspected from its typer app and the SDK surface from its ``Client`` — so
an overview reflects the exact installed version (not readthedocs). The
per-service command sequences are curated here and filled from the caller's
context; ``tests/test_commands.py`` drift-guards that every referenced command
and method still exists in the imported package.

v1: a deliberately small first cut — refine later.
"""

from __future__ import annotations

import inspect
from typing import Any

import typer
from unitysvc import AccessPlan, Client
from unitysvc.cli import app as _cli_app

from .render import RenderContext

_SDK_RESOURCES = ("groups", "services", "secrets", "enrollments")


# --- introspection of the imported package --------------------------------


def cli_command_tree() -> list[tuple[str, str]]:
    """Every leaf ``usvc`` command + its short help, from the typer app."""
    root = typer.main.get_command(_cli_app)
    out: list[tuple[str, str]] = []

    def walk(command: Any, prefix: str) -> None:
        for name, sub in (getattr(command, "commands", {}) or {}).items():
            path = f"{prefix} {name}".strip()
            if getattr(sub, "commands", None):
                walk(sub, path)
            else:
                help_text = (getattr(sub, "short_help", None) or sub.help or "").strip()
                out.append((f"usvc {path}", help_text.split("\n")[0]))

    walk(root, "")
    return sorted(out)


def _sdk_client() -> Client:
    # A never-connected client — resources instantiate lazily and no request is
    # made until a method is called, so this only exposes the surface.
    return Client(base_url="https://unitysvc.invalid/v1")


def sdk_surface() -> list[tuple[str, list[tuple[str, str, str]]]]:
    """Per resource: ``[(method, signature, first docstring line)]``."""
    client = _sdk_client()
    out: list[tuple[str, list[tuple[str, str, str]]]] = []
    for resource in _SDK_RESOURCES:
        obj = getattr(client, resource)
        methods = []
        for name in sorted(m for m in dir(obj) if not m.startswith("_")):
            attr = getattr(obj, name)
            if not callable(attr):
                continue
            try:
                signature = str(inspect.signature(attr))
            except (TypeError, ValueError):
                signature = "(...)"
            doc = (inspect.getdoc(attr) or "").split("\n", 1)[0].strip()
            methods.append((name, signature, doc))
        out.append((resource, methods))
    return out


# --- helpers over the access plan -----------------------------------------


def _unset_required_secrets(plan: AccessPlan, set_names: frozenset[str]) -> list[str]:
    names: list[str] = []
    channels = plan.channels if isinstance(plan.channels, list) else []
    for channel in channels:
        secrets = channel.required_secrets if isinstance(channel.required_secrets, list) else []
        for secret in secrets:
            name = secret.name if isinstance(secret.name, str) else None
            if name and name not in set_names and name not in names:
                names.append(name)
    return names


def _needs_enrollment(plan: AccessPlan) -> bool:
    mode = plan.enrollment_mode if isinstance(plan.enrollment_mode, str) else "disallowed"
    return mode != "disallowed"


def _endpoint_url(plan: AccessPlan, context: RenderContext) -> str | None:
    if context.enrollment_urls:
        return context.enrollment_urls[0]
    interfaces = plan.interfaces if isinstance(plan.interfaces, list) else []
    for interface in interfaces:
        if isinstance(interface.base_url, str) and interface.base_url:
            return interface.base_url
    return None


def _fence(lang: str, *lines: str) -> list[str]:
    return [f"```{lang}", *lines, "```", ""]


# --- overviews (no service): the introspected surface ----------------------


def cli_overview() -> str:
    out = ["# unitysvc-py CLI (`usvc`)", ""]
    for path, help_text in cli_command_tree():
        out.append(f"- `{path}`" + (f" — {help_text}" if help_text else ""))
    return "\n".join(out).strip() + "\n"


def sdk_overview() -> str:
    out = [
        "# unitysvc-py SDK (Python)",
        "",
        *_fence(
            "python",
            "from unitysvc import Client",
            "client = Client()  # UNITYSVC_API_KEY from env",
        ),
    ]
    for resource, methods in sdk_surface():
        out.append(f"## client.{resource}")
        out += [
            f"- `client.{resource}.{name}{signature}`" + (f" — {doc}" if doc else "")
            for name, signature, doc in methods
        ]
        out.append("")
    return "\n".join(out).strip() + "\n"


def endpoints_overview() -> str:
    return (
        "# Raw HTTP\n\n"
        "Pass a `service_id` to get the curl to call a specific service. Account "
        "operations (secrets, enrollments) are easier via `customer_cli` / "
        "`customer_sdk`, which target the same customer API."
    )


# --- per-service command sequences -----------------------------------------


def render_cli(service_id: str, plan: AccessPlan, context: RenderContext) -> str:
    out = ["# Use this service from the `usvc` CLI", ""]
    unset = _unset_required_secrets(plan, context.set_secret_names)
    if unset:
        out.append("## Set the secrets it needs")
        out += _fence("bash", *[f"usvc secrets set {name}" for name in unset])
    if _needs_enrollment(plan):
        out.append("## Enroll")
        out += _fence("bash", f"usvc services enroll {service_id}")
    out.append("## Call it")
    out += _fence("bash", f"usvc services dispatch {service_id} --json '{{...}}'")
    return "\n".join(out).strip() + "\n"


def render_sdk(service_id: str, plan: AccessPlan, context: RenderContext) -> str:
    lines = ["from unitysvc import Client", "", "client = Client()  # UNITYSVC_API_KEY from env"]
    for name in _unset_required_secrets(plan, context.set_secret_names):
        lines.append(f'client.secrets.set("{name}", value="...")')
    if _needs_enrollment(plan):
        lines.append(f'client.enrollments.create(service_id="{service_id}")')
    lines.append(f'resp = client.services.dispatch("{service_id}", json={{...}})')
    body = ["# Use this service from Python (unitysvc-py)", "", *_fence("python", *lines)]
    return "\n".join(body).strip() + "\n"


def render_endpoints(service_id: str, plan: AccessPlan, context: RenderContext) -> str:
    out = ["# Call this service over raw HTTP", ""]
    url = _endpoint_url(plan, context)
    if url is None:
        out.append(
            "Enroll first (see `customer_cli`); your endpoint is then your "
            "per-enrollment `/e/<CODE>` URL."
        )
        return "\n".join(out).strip() + "\n"
    out += _fence(
        "bash",
        f"curl -X POST '{url}' \\",
        "  -H 'Authorization: Bearer $UNITYSVC_API_KEY' \\",
        "  -H 'Content-Type: application/json' \\",
        "  -d '{...}'",
    )
    unset = _unset_required_secrets(plan, context.set_secret_names)
    if unset:
        out.append("Set first (see `customer_cli`): " + ", ".join(f"`{name}`" for name in unset))
    return "\n".join(out).strip() + "\n"
