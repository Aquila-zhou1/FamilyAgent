# One image, three processes (web / mcp-openings / mcp-lichess); the command differs per Deployment.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv

WORKDIR /app
# Dependencies first (cached layer): resolved strictly from uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY familyagent ./familyagent
COPY eval/fixtures ./eval/fixtures

RUN useradd -r -u 10001 app
USER 10001

EXPOSE 8000 8001 8002
CMD ["python", "-m", "familyagent"]
