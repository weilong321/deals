FROM ghcr.io/astral-sh/uv:0.5.14 AS uv

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-install-project

COPY client ./client
COPY flows ./flows
COPY parsers ./parsers
COPY schema ./schema
COPY data ./data
COPY prefect.yaml ./prefect.yaml

ENV PATH="/app/.venv/bin:$PATH"

VOLUME ["/app/data"]

CMD ["python", "-m", "flows.ozbargain.latest_deals"]
