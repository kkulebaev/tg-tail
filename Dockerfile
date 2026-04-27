FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini entrypoint.sh ./

RUN uv sync --frozen --no-dev \
    && chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:${PATH}"

ENTRYPOINT ["/app/entrypoint.sh"]
