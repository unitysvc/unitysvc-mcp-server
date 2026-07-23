"""Generic in-process introspection, shared by the customer and seller command
generators (``commands.py`` / ``seller_commands.py``).

Command *shapes* are anchored to whatever SDK package is passed in — the CLI
tree from a typer app, the SDK surface from a constructed ``Client`` and its
resource names — so an overview reflects the exact installed version (not
readthedocs). Kept free of any package import so it has no opinion about
*which* SDK it is walking.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from typing import Any

import typer


def cli_command_tree(app: typer.Typer, prog: str = "usvc") -> list[tuple[str, str]]:
    """Every leaf command + its short help, from a typer app.

    ``prog`` prefixes each path (the program name a user would actually type —
    typer apps do not reliably carry their own).
    """
    root = typer.main.get_command(app)
    out: list[tuple[str, str]] = []

    def walk(command: Any, prefix: str) -> None:
        for name, sub in (getattr(command, "commands", {}) or {}).items():
            path = f"{prefix} {name}".strip()
            if getattr(sub, "commands", None):
                walk(sub, path)
            else:
                help_text = (getattr(sub, "short_help", None) or sub.help or "").strip()
                out.append((f"{prog} {path}", help_text.split("\n")[0]))

    walk(root, "")
    return sorted(out)


def sdk_surface(
    client: Any, resources: Sequence[str]
) -> list[tuple[str, list[tuple[str, str, str]]]]:
    """Per resource: ``[(method, signature, first docstring line)]``.

    ``client`` is a constructed (but never-connected) SDK client — resources
    instantiate lazily and no request is made until a method is called, so
    passing one only exposes the surface.
    """
    out: list[tuple[str, list[tuple[str, str, str]]]] = []
    for resource in resources:
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


def fence(lang: str, *lines: str) -> list[str]:
    return [f"```{lang}", *lines, "```", ""]
