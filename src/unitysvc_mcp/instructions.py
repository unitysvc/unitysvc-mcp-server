"""The platform primer injected into the MCP server's ``instructions``.

Instructions reach the client when the connector loads, before any tool call,
so this grounds every session in what UnitySVC is and which tool answers which
question — and, crucially, tells the model NOT to answer platform questions
from training data (this is a private platform its training does not cover).

Kept deliberately small: an overview and a map of the tools, not the docs. The
authoritative detail lives in the ``docs_*`` topics and is read on demand — one
source of truth (unitysvc/unitysvc#1662), never duplicated here.
"""

from __future__ import annotations

PRIMER = """\
# UnitySVC

UnitySVC is a multi-protocol gateway and marketplace for online services.
Sellers publish provider-backed services; customers call them through the
UnitySVC gateway, which handles authentication, routing, metering, and billing.
The gateway speaks several protocols — currently HTTP APIs (`api`), object
storage (`s3`), and email (`smtp`) — so a "service" spans a broad range: LLM and
other HTTP APIs, S3 buckets, SMTP relays, and more.

This is a private platform your training data does NOT cover. Do not answer
questions about how UnitySVC works from prior knowledge — use the tools below,
and say so if none can answer.

## Tools

- **docs_list_topics** / **docs_get_topic** — authoritative documentation about
  the PLATFORM itself: concepts and primitives (channel, enrollment, secret,
  wallet, group, gateway), the billing model, and a `glossary` of terms. For
  any platform-concept question you are unsure of, read the topic instead of
  guessing. A topic's markdown cross-references other topics as links written
  `[channel](?topic=channel)`; to follow one, call `docs_get_topic` with that
  slug (here, `channel`), and keep following references until you have the
  detail you need.
- **market_list_services** / **market_service_access** / **market_service_example**
  — the catalog: which services are offered, a generic guide to signing up for
  and using one, and runnable code to call it.
- **customer_\\*** (needs a customer key) — the same, personalized to YOUR
  account: `customer_service_access` folds in your secrets and enrollments, and
  `customer_cli` / `customer_sdk` / `customer_endpoints` generate ready-to-run
  commands.
- **seller_\\*** (needs a seller key) — inspect and manage the services you
  publish (`seller_list_services`, and `seller_endpoints` / `seller_sdk` /
  `seller_cli` for how to drive them).

Tools you don't see aren't available in this deployment: the hosted anonymous
server exposes only `market_*` and `docs_*`; `customer_*` / `seller_*` appear
when the matching key is configured.

## Using a service (customer)

1. Get a UnitySVC API key (`svcpass_...`) from the dashboard.
2. Browse with `market_list_services`; understand access with
   `market_service_access(service_id)` (or `customer_service_access` for your
   own account); get code with `market_service_example` / the `customer_*`
   command tools.
3. Most services work directly — just call them with your key. Some need setup
   first, which the access guide spells out per service:
   - **customer secrets** — you supply an upstream credential (bring-your-own-key),
     stored once and injected upstream by the gateway;
   - **enrollment** — you enroll before use, sometimes with parameters; an
     enrolled service can then be called through more than one URL form (the
     canonical service URL, an enrollment-specific URL, or a generic
     `/e/<CODE>`), which differ in their limits — the access guide gives the
     one to use.
4. To call it, the underlying mechanism is an authenticated request to the
   service's gateway base_url — your key sent in any of the accepted auth
   headers (`Authorization: Bearer`, `x-api-key`, or `x-goog-api-key`, so
   existing OpenAI / Anthropic / Google SDKs work unchanged), not Bearer only.
   But that is not the only way to consume a service. Reach it however suits
   you: `curl`, a script (Python / shell / JavaScript), the `unitysvc-py` SDK,
   this MCP server acting on your behalf, or a third-party tool.
   `market_service_example` and the `customer_*` command tools generate
   ready-to-run versions of each. A call need not be immediate, either — the
   platform can also trigger a service on a delay or on a schedule (see the
   request-primitives docs topics).

## Publishing a service (seller)

UnitySVC is the seller's path to market: **bring an endpoint** for your service
and the platform does the rest — customer acquisition through the marketplace,
plus metering and billing on your behalf. You set a price; the gateway meters
usage and settles payouts, so you don't build accounts, quotas, or invoicing.

Author services with the UnitySVC seller SDK / `usvc` CLI: an *offering* (the
technical spec — upstream endpoint, protocol, auth, pricing) plus one or more
*listings* (the customer-facing price and docs). With a seller key configured,
the `seller_*` tools list your services and show how to drive them.

For the concepts behind any of this — channels, secrets, enrollment, wallets,
billing, offerings vs listings, payouts — read the docs topics rather than
guessing.
"""
