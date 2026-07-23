# UnitySVC MCP Server — developer context

A **thin MCP adapter** exposing the UnitySVC marketplace, account operations, and platform
docs to MCP clients (Claude Code/Desktop, Codex, claude.ai). Business rules, visibility,
billing, and authorization stay in the UnitySVC backend — this package only adapts MCP calls
to the UnitySVC APIs (via the official `unitysvc-py` / `unitysvc-sellers` SDKs) and the docs
site. Python 3.12+, `mcp[cli]`, pydantic v2, httpx. See the README for the product framing.

## Commands (uv-managed)

```bash
uv sync                       # install deps into .venv
uv run pytest -q              # tests (pytest + pytest-asyncio; async tests need @pytest.mark.asyncio)
uv run ruff check .           # lint  (CI runs this)
uv run ruff format .          # apply formatting  (CI checks `ruff format --check`)
uv run unitysvc-mcp-server    # run the server (stdio by default)
```

CI (`.github/workflows`) runs ruff check, ruff format --check, pytest, and a Docker build.

## Two deployments, one package

Same code, differing only in transport and whether the environment carries credentials:

- **stdio** (default) — a subprocess of the user's MCP client, holding *their* keys. Full surface.
- **http** — the hosted `mcp.unitysvc.com`, run with an **empty environment**, so only the
  credential-free tools register and there is no key to hold, log, or leak.

## Architecture (the load-bearing conventions)

- **`tools/<domain>.py` — the module a tool lives in *is* its access rule, stated by its
  `<domain>_` name prefix:**

  | prefix | credential | registered |
  |---|---|---|
  | `market_` | none | always |
  | `docs_` | none | always |
  | `seller_` | `UNITYSVC_SELLER_API_KEY` | when that key is set |

  `market_` and `docs_` are both free but distinct: `market_` is the service **catalog**
  (what to buy, how to call it); `docs_` is the platform **documentation** (concepts,
  primitives, glossary). `register_tools` in `server.py` decides the surface once, at startup,
  from the environment. To add a tool: put it in the module matching its credential, prefix its
  name accordingly, and add it in that module's `register()`. `test_modes.py` asserts the
  prefix matches the module and that the anonymous set is exactly the credential-free tools.

- **`clients/` — one client per backend, named for the API not the SDK.** `CustomerApi` /
  `SellerApi` wrap the SDKs; `DocsClient` is different — it fetches the **frontend site**
  (`/topics`, `/topics/<slug>`) directly with httpx (no SDK, no credential) and holds a small
  in-memory TTL cache. All three hang off `AppContext` (built in the server lifespan).

- **Credentials come from the environment only** — never from request headers (that would be
  the token-passthrough pattern the MCP spec forbids; `test_modes.py` guards it). Keys are
  passed **per call**, so a client holding a key ≠ every call using it (the market tools call
  the customer API *anonymously*). **Presence of a key is the only role signal** — `svcpass_`
  keys encode the role and the backend authorizes every call; the server never infers a role.

## Config (`settings.py`, env-driven; names match the SDKs' own)

`UNITYSVC_SELLER_API_KEY`, `UNITYSVC_API_URL`, `UNITYSVC_SELLER_API_URL`,
`UNITYSVC_SITE_URL` (docs host, default `https://unitysvc.com`),
`UNITYSVC_DOCS_CACHE_TTL` (docs cache seconds, default 900),
`UNITYSVC_MCP_TRANSPORT` / `_HOST` / `_PORT`. See `.env.example`.

> stdio note: exporting these in your shell does **not** reach a stdio MCP server — clients
> pass only a safelist. Declare them in your MCP client config (see README).

## Docs tools specifics

The `docs_*` tools read the single-source docs "topics" from the frontend
(unitysvc/unitysvc#1637). `docs_list_topics` → the `{slug, title}` menu; `docs_get_topic(slug)`
→ that topic's markdown (frontmatter stripped, title as an H1). The `glossary` is just a topic
(`docs_get_topic("glossary")`), not a separate tool. Slugs are validated against
`^[A-Za-z0-9_-]+$` before any request (the unitysvc#1662 path-traversal guard). Returning
markdown (not structured JSON) is deliberate — an LLM digests prose better, matching
`market_service_access`.
