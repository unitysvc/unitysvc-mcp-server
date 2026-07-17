# UnitySVC MCP Server

Starter implementation for a hosted UnitySVC MCP server using the MCP Python SDK v2 beta.

## What This Includes

- Bearer-token authentication plumbing.
- Anonymous/customer catalog service listing.
- Seller-owned service listing.
- A role-aware `list_services` tool:
  - anonymous/customer sessions list catalog-visible services;
  - seller sessions list the authenticated seller's own services.
- Explicit aliases:
  - `list_catalog_services`
  - `list_seller_services`

This is intentionally thin: it adapts MCP calls to UnitySVC HTTP APIs. Business rules, billing,
visibility, and authorization should remain enforced by the UnitySVC backend.

## Install

```bash
uv sync --dev
cp .env.example .env
```

## Run

```bash
uv run mcp dev src/unitysvc_mcp/server.py
```

For a hosted Streamable HTTP process:

```bash
uv run uvicorn unitysvc_mcp.server:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/healthz
```

MCP endpoint:

```text
http://localhost:8000/mcp
```

The MCP SDK v2 beta is pinned in `pyproject.toml`. Revisit the pin when v2 reaches a stable release.

## Container

```bash
docker build -t unitysvc-mcp-server .
docker run --rm -p 8000:8000 --env-file .env unitysvc-mcp-server
```

Images are published to GitHub Container Registry:

```text
ghcr.io/unitysvc/unitysvc-mcp-server
```

## Authentication Model

Clients should send an OAuth bearer token with MCP HTTP requests. The starter supports two modes:

1. Development tokens via `UNITYSVC_MCP_DEV_TOKENS`.
2. Optional OAuth/OIDC introspection via `UNITYSVC_AUTH_INTROSPECTION_URL`.

If no token is present, the principal is anonymous. Anonymous users can call catalog read-only tools.
Seller-only tools require a token whose resolved principal has the `seller` role.

## Tool Contract

`list_services(status=None, limit=25, cursor=None)`

Role-aware convenience tool. It returns catalog services for anonymous/customer principals and seller-owned
services for seller principals.

`list_catalog_services(group=None, limit=25, cursor=None)`

Read-only catalog listing for anonymous/customer flows.

`list_seller_services(status=None, limit=25, cursor=None)`

Seller-owned service listing. Requires the `seller` role.
