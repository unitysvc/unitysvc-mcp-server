# UnitySVC MCP Server

Exposes the UnitySVC catalog and account operations to MCP clients — Claude Code, Claude
Desktop, Codex, claude.ai — so an agent can discover services, explain how to call them,
and (when you supply credentials) operate your account.

It is deliberately thin: it adapts MCP calls to the UnitySVC APIs through the official
`unitysvc-py` and `unitysvc-sellers` SDKs. Business rules, visibility, billing, and
authorization stay in the UnitySVC backend.

> **Status.** Prototype. The table below marks what runs today versus what is designed but
> not yet built. See unitysvc/unitysvc#1492 for the full design.
>
> | | Status |
> |---|---|
> | Market + seller listing tools via the official SDKs | ✅ implemented |
> | Anonymous marketplace browsing (no credentials) | ✅ implemented |
> | stdio transport (default) and HTTP (opt-in) | ✅ implemented |
> | Credentials from `UNITYSVC_API_KEY` / `UNITYSVC_SELLER_API_KEY` | ✅ implemented |
> | Tools split by mode, advertised on credentials present | ✅ implemented |
> | PyPI publish workflow | ✅ implemented — awaiting a PyPI trusted publisher and a release |
> | Published to PyPI (`uvx unitysvc-mcp-server`) | ⏳ not yet released — install from source |
> | `mcp.unitysvc.com` deployed | ⏳ not yet deployed |
> | `how_to_call` code-generation tool | ⏳ planned |
>
> The earlier role-inference bug — where a valid *seller* key resolved to a customer
> principal and seller tools rejected it — is fixed by removing role inference entirely.

## Two modes

The same package runs in two shapes. They differ only in transport and where credentials
come from — the tools themselves are identical.

| | **Local (stdio)** | **Hosted (HTTP)** |
|---|---|---|
| Runs as | a subprocess of your MCP client, on your machine | a service at `mcp.unitysvc.com` |
| Credentials | your own API keys, from the process environment | **none — by design** |
| Offers | everything: the market view, plus your customer and seller operations | market discovery and how-to guidance only |
| Reaches | Claude Code, Claude Desktop, Codex | any client, **including claude.ai in a browser** |
| Needs | a local Python runtime | nothing |

**Why the hosted instance holds no credentials.** The valuable question — *"which service
should I use, and how do I call it?"* — does not require your key. The catalog is public,
and the actual invocation goes from your machine to the gateway with your key, never
through us. So the hosted server answers questions and returns copy-pasteable commands; it
never acts on your behalf, and there is no credential for it to hold, log, or leak.

It is not a different program. It is this same package running with nothing in its
environment, so only the tools that need no credentials are advertised.

## Credentials: where they live, and what is never sent

This is the part worth reading carefully.

### Local (stdio)

```
   your MCP client config
        │  populates the child process environment at spawn
        ▼
   unitysvc-mcp-server  (subprocess on your machine)
        │  UNITYSVC_API_KEY / UNITYSVC_SELLER_API_KEY
        ▼  HTTPS, directly
   api.unitysvc.com  /  seller.unitysvc.com
```

- Your key lives in **your MCP client's configuration** and in the **environment of a
  process on your own machine**. Nowhere else.
- It is sent **only to the UnitySVC API**, over HTTPS, by the SDK — the same destination
  the `usvc` CLI uses. There is no intermediary.
- It is **never** sent to `mcp.unitysvc.com`, and never appears in tool arguments, so it
  does not enter the model's context, the conversation transcript, or your client's logs.

**Exporting the variable in your shell is not enough.** MCP clients pass only a *safelist*
of variables to a spawned server — `HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM`, `USER` — so
`UNITYSVC_API_KEY` from your shell profile will **not** reach the process. You must declare
it in the MCP configuration. Use variable expansion so the value stays in your shell rather
than being written into a file:

```jsonc
"env": { "UNITYSVC_API_KEY": "${UNITYSVC_API_KEY}" }
```

Which key you provide decides what you can do:

| You set | You get |
|---|---|
| nothing | marketplace browsing only (anonymous) |
| `UNITYSVC_API_KEY` | marketplace + customer operations |
| `UNITYSVC_SELLER_API_KEY` | marketplace + seller operations |
| both | everything (a seller who is also a customer) |

There is no role to configure. The API key already encodes whether it is a customer or a
seller key, and the backend enforces it.

### Hosted (HTTP)

No credentials are configured, sent, or held. If you find yourself pasting an API key to
use `mcp.unitysvc.com`, something is wrong — it does not accept one.

## Installation

### Claude Code — local, with your keys

```bash
claude mcp add unitysvc \
  --env UNITYSVC_API_KEY="${UNITYSVC_API_KEY}" \
  --env UNITYSVC_SELLER_API_KEY="${UNITYSVC_SELLER_API_KEY}" \
  -- uvx unitysvc-mcp-server
```

Or project-scoped, in `.mcp.json` — safe to commit, since the values are expanded from your
environment at launch and never written into the file:

```jsonc
{
  "mcpServers": {
    "unitysvc": {
      "type": "stdio",
      "command": "uvx",
      "args": ["unitysvc-mcp-server"],
      "env": {
        "UNITYSVC_API_KEY": "${UNITYSVC_API_KEY}",
        "UNITYSVC_SELLER_API_KEY": "${UNITYSVC_SELLER_API_KEY}"
      }
    }
  }
}
```

Omit either variable to run without that role's tools; omit both for anonymous browsing.

### Claude Desktop — local, with your keys

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```jsonc
{
  "mcpServers": {
    "unitysvc": {
      "type": "stdio",
      "command": "uvx",
      "args": ["unitysvc-mcp-server"],
      "env": { "UNITYSVC_API_KEY": "svcpass_..." }
    }
  }
}
```

Claude Desktop is a GUI application and does not read your shell startup files, so `${VAR}`
expansion has nothing to expand from — the literal value is required here. That file is not
in a repository, but treat it as a secret. Restart Claude Desktop after editing, and note
that a JSON syntax error silently disables *all* configured servers.

### Codex — local, with your keys

Codex takes an equivalent stdio entry in `~/.codex/config.toml` with `command`, `args`, and
`env`. Check the current Codex documentation for the exact key names before relying on it —
we have not verified them against a recent release.

### claude.ai — hosted, no credentials

Add `https://mcp.unitysvc.com/mcp` as a custom connector. There is nothing to authenticate
and no key to supply. You get catalog discovery and how-to guidance; to act on your account,
use one of the local setups above.

## Tools

Named for the *side of the marketplace* they belong to, so it is unambiguous which one
answers a given request:

| Tool | View | Credential | In hosted mode |
|---|---|---|---|
| `list_market_services(group, limit, cursor)` | what you can **buy** — services on offer | none — uses `UNITYSVC_API_KEY` if set | ✅ always |
| `list_seller_services(status, limit, cursor)` | what you **sell** — your own listings | `UNITYSVC_SELLER_API_KEY` | — never |

Each tool's description states explicitly what it is *not* and points at the other, since
those descriptions are all a model has when choosing between them.

**Tools are advertised, not just gated.** With no seller key, `list_seller_services` does
not appear in `tools/list` at all, so an agent never sees an option it cannot use and never
burns a turn discovering that. The hosted deployment runs with an empty environment, so it
advertises exactly the first row.

The previous role-aware `list_services` has been removed. It existed to paper over an agent
not knowing which mode it was in; conditional advertisement answers that directly, and the
tool was redundant with the two explicit ones in both modes.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `UNITYSVC_API_KEY` | customer API key | unset → anonymous |
| `UNITYSVC_SELLER_API_KEY` | seller API key | unset → seller tools unavailable |
| `UNITYSVC_API_URL` | customer API base | `https://api.unitysvc.com/v1` |
| `UNITYSVC_SELLER_API_URL` | seller API base | `https://seller.unitysvc.com/v1` |
| `UNITYSVC_MCP_TRANSPORT` | `stdio` or `http` | `stdio` |
| `UNITYSVC_MCP_HOST` / `UNITYSVC_MCP_PORT` | bind address — HTTP mode only | `127.0.0.1` / `8000` |

The key and URL variables are the SDKs' own, so if you already use the `usvc` CLI you have
them set and need no new values.

Anonymous catalog browsing requires the customer API to serve unauthenticated catalog reads
(unitysvc/unitysvc#1610) — merged, but not yet deployed in every environment.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check src/ tests/
```

Run it:

```bash
uv run unitysvc-mcp-server                              # stdio (default)
UNITYSVC_MCP_TRANSPORT=http uv run unitysvc-mcp-server  # HTTP, binds HOST:PORT
```

The startup log line reports which mode you got — transport, whether any credentials were
found, and the tools registered.

The MCP SDK v2 beta is pinned in `pyproject.toml`; revisit the pin when v2 stabilises.

## Design

See unitysvc/unitysvc#1492 for the full design: the two deployment modes, credential
handling, MCP specification conformance, and phasing.
