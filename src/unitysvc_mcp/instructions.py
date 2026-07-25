"""The platform primer injected into the MCP server's ``instructions``.

Instructions reach the client when the connector loads, before any tool call,
so this grounds every session in what UnitySVC is and which tool answers which
question — and, crucially, tells the model NOT to answer platform questions
from training data (this is a private platform its training does not cover).

Kept deliberately small: an overview and a map of the tools, not the docs. The
authoritative detail lives in the platform topics and is fetched on demand via
``platform_read_topic`` — one source of truth, never duplicated here.
"""

from __future__ import annotations

PRIMER = """\
# UnitySVC

UnitySVC is a marketplace for LLM and API services. Sellers publish
provider-backed services; customers call them through the UnitySVC gateway,
which handles authentication, routing, and billing.

This is a private platform your training data does NOT cover. Do not answer
questions about how UnitySVC works from prior knowledge — use the tools below,
and say so if a tool cannot answer.

## Tools

- **platform_list_topics** / **platform_read_topic** — authoritative
  documentation about the PLATFORM itself: what a channel, enrollment, secret,
  wallet, group, or gateway is; how pricing and billing work; and so on. For
  any platform-concept question you are not certain of, read the relevant topic
  instead of guessing. Topics cross-reference each other with links written as
  `[channel](?topic=channel)` — to follow one, call `platform_read_topic` with
  that slug (here, `channel`). When a topic isn't enough, read the topics it
  references.
- **market_list_services** / **market_service_access** / **market_service_example**
  — the catalog: which services are on offer, how to sign up for and use a
  specific one, and runnable code to call it.
- **seller_\\*** — seller publishing/management tools, present only when this
  server is configured with a seller API key.

## Using a service (customer)

1. Get a UnitySVC API key (`svcpass_...`) from the dashboard.
2. Browse with `market_list_services`; understand access with
   `market_service_access(service_id)`; get code with
   `market_service_example(service_id)`.
3. Set any required secrets or enroll as that guide says, then call the
   service's gateway base_url with your key as a Bearer token.

For the concepts behind any of this — channels, secrets, enrollment, wallets,
billing, groups — read the platform topics rather than guessing.
"""
