# Optional Linux worker recipe. Build from the repository root:
# docker build -f deploy/Dockerfile -t rdc-worker .
# Hardware/OS qualification is recorded in docs/platforms.md.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright PATH=/opt/rdc/bin:$PATH \
    RDC_STATE_DIR=/home/rdc/state RDC_DESKTOP_MODE=disabled RDC_ENABLE_EXEC=0
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-tk ca-certificates xvfb xauth openbox scrot socat \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /bin/sh rdc \
    && python3 -m venv /opt/rdc
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir '.[browser,desktop]' \
    && python -m playwright install --with-deps chromium \
    && chmod -R a+rX /opt/playwright \
    && mkdir -p /workspace /home/rdc/state \
    && chown -R rdc:rdc /workspace /home/rdc/state \
    && chmod 700 /home/rdc/state
USER rdc
WORKDIR /workspace
EXPOSE 8765
ENTRYPOINT ["/bin/sh", "/app/deploy/entrypoint.sh"]
