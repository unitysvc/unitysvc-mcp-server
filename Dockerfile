FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app/

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first so the layer caches across source-only changes.
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY ./pyproject.toml ./uv.lock ./README.md /app/
COPY ./src /app/src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

# A container image IS the HTTP deployment — the stdio path is `pip`/`uvx` on
# the user's own machine, where there is no port to expose. The server itself
# defaults to stdio, so the transport has to be set here or `docker run` starts
# a stdio server that ignores the port below and can never be reached.
ENV UNITYSVC_MCP_TRANSPORT=http

# The SDK defaults to binding 127.0.0.1, which is unreachable from outside the
# container. Binding 0.0.0.0 also leaves the SDK's DNS-rebinding protection off
# (it only auto-enables for loopback hosts) — fine behind an ingress that
# terminates and validates external traffic.
ENV UNITYSVC_MCP_HOST=0.0.0.0
ENV UNITYSVC_MCP_PORT=8000

# Credentials are deliberately absent. The server registers tools from its
# environment, so an empty one keeps this image anonymous and context-only:
# it advertises market_* and nothing else, with no key to hold, log, or leak.
# A deployment that sets UNITYSVC_API_KEY / UNITYSVC_SELLER_API_KEY here would
# make every caller act as whoever owns that key.

EXPOSE 8000

CMD ["unitysvc-mcp-server"]
