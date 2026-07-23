"""Generate how-to-manage output for a service, from the seller's side.

Command *shapes* are anchored to the in-process ``unitysvc-sellers`` — the CLI
tree is introspected from its typer app (``usvc_seller``) and the SDK surface
from its ``Client`` — via ``introspect.py``, shared with ``commands.py``. The
per-service command sequences are curated here and filled from the caller's
own inventory (``SellerContext``); ``tests/test_seller_commands.py``
drift-guards that every referenced command and method still exists in the
imported package.

v1: a deliberately small first cut — refine later.
"""

from __future__ import annotations

from unitysvc_sellers import Client
from unitysvc_sellers.cli import app as _cli_app

from . import introspect
from .seller_context import SellerServiceInfo

# Verified seller resource properties: services, documents, files, groups,
# instances, promotions, secrets, tasks, templates.
SELLER_RESOURCES = (
    "documents",
    "files",
    "groups",
    "instances",
    "promotions",
    "secrets",
    "services",
    "tasks",
    "templates",
)

_PROG = "usvc_seller"

# Statuses that mean "not yet submitted" — the next step is to submit it.
_UNSUBMITTED_STATUSES = {None, "draft"}


# --- introspection of the imported package ----------------------------------


def cli_command_tree() -> list[tuple[str, str]]:
    """Every leaf ``usvc_seller`` command + its short help, from the typer app."""
    return introspect.cli_command_tree(_cli_app, prog=_PROG)


def _sdk_client() -> Client:
    # unitysvc-sellers' Client requires an api_key (unlike unitysvc-py's,
    # which allows None) — a placeholder is fine here: resources instantiate
    # lazily and no request is made until a method is called, so this only
    # exposes the surface.
    return Client(api_key="svcpass_x", base_url="https://unitysvc.invalid/v1")


def sdk_surface() -> list[tuple[str, list[tuple[str, str, str]]]]:
    """Per resource: ``[(method, signature, first docstring line)]``."""
    return introspect.sdk_surface(_sdk_client(), SELLER_RESOURCES)


# --- overviews (no service): the introspected surface -----------------------


def cli_overview() -> str:
    out = [f"# unitysvc-sellers CLI (`{_PROG}`)", ""]
    for path, help_text in cli_command_tree():
        out.append(f"- `{path}`" + (f" — {help_text}" if help_text else ""))
    return "\n".join(out).strip() + "\n"


def sdk_overview() -> str:
    out = [
        "# unitysvc-sellers SDK (Python)",
        "",
        *introspect.fence(
            "python",
            "from unitysvc_sellers import Client",
            'client = Client(api_key="...")  # UNITYSVC_SELLER_API_KEY from env',
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
        "The seller API has no documented raw-HTTP surface for managing a "
        "service directly. Use `seller_cli` / `seller_sdk` instead, which "
        "target the same seller API."
    )


# --- per-service command sequences -----------------------------------------


def _status_line(info: SellerServiceInfo | None) -> str | None:
    if info is None or not info.status:
        return None
    return f"Current status: `{info.status}`."


def render_cli(service_id: str, info: SellerServiceInfo | None) -> str:
    out = ["# Manage this service from the `usvc_seller` CLI", ""]
    status_line = _status_line(info)
    if status_line:
        out += [status_line, ""]
    out.append("## Inspect")
    out += introspect.fence("bash", f"{_PROG} services show {service_id}")
    status = info.status if info is not None else None
    if status in _UNSUBMITTED_STATUSES:
        out.append("## Submit for review")
        out += introspect.fence("bash", f"{_PROG} services submit {service_id}")
    else:
        out.append("## Update or re-test")
        out += introspect.fence(
            "bash",
            f"{_PROG} services update {service_id} --field value",
            f"{_PROG} services run-tests {service_id}",
        )
    return "\n".join(out).strip() + "\n"


def render_sdk(service_id: str, info: SellerServiceInfo | None) -> str:
    lines = [
        "from unitysvc_sellers import Client",
        "",
        'client = Client(api_key="...")  # UNITYSVC_SELLER_API_KEY from env',
        f'service = client.services.get("{service_id}")',
    ]
    status = info.status if info is not None else None
    if status in _UNSUBMITTED_STATUSES:
        lines.append(f'client.services.submit_for_review("{service_id}")')
    else:
        lines.append(f'client.services.update("{service_id}", body={{...}})')
        lines.append(f'client.services.run_tests("{service_id}")')
    body = [
        "# Manage this service from Python (unitysvc-sellers)",
        "",
        *introspect.fence("python", *lines),
    ]
    status_line = _status_line(info)
    if status_line:
        body.insert(2, status_line)
        body.insert(3, "")
    return "\n".join(body).strip() + "\n"


def render_endpoints(service_id: str, info: SellerServiceInfo | None) -> str:
    out = [
        "# Raw HTTP",
        "",
        f"The seller API has no documented raw-HTTP surface for managing "
        f"`{service_id}` directly. Use `seller_cli` / `seller_sdk` instead, "
        "which target the same seller API.",
    ]
    status_line = _status_line(info)
    if status_line:
        out += ["", status_line]
    return "\n".join(out).strip() + "\n"
