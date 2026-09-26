FROM python:3.12-slim-bookworm AS build

WORKDIR /build
COPY pyproject.toml README.md LICENSE docker-requirements.txt ./
COPY src/ ./src/
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels -r docker-requirements.txt \
    && python -m pip wheel --no-cache-dir --no-deps --wheel-dir /wheels .

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLAMORIS_INTELLIGENCE_TRANSPORT=streamable-http

COPY --from=build /wheels /wheels
COPY docker-requirements.txt /tmp/docker-requirements.txt
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels \
      -r /tmp/docker-requirements.txt /wheels/flamoris_intelligence_mcp-*.whl \
    && rm -rf /wheels /tmp/docker-requirements.txt \
    && mkdir /app

USER 10001:10001
WORKDIR /app
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-m", "flamoris_intelligence_mcp.healthcheck"]
CMD ["flamoris-intelligence-mcp", "--transport", "streamable-http"]
