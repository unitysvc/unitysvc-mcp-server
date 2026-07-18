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

# The SDK defaults to binding 127.0.0.1, which is unreachable from outside the
# container. Binding 0.0.0.0 also leaves the SDK's DNS-rebinding protection off
# (it only auto-enables for loopback hosts) — fine behind an ingress that
# terminates and validates external traffic.
ENV UNITYSVC_MCP_HOST=0.0.0.0
ENV UNITYSVC_MCP_PORT=8000

EXPOSE 8000

CMD ["unitysvc-mcp-server"]
