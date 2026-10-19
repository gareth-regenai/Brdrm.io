# The API and the worker, for running the whole app on a laptop (docs/run-locally.md).
# Render builds from render.yaml instead; this image is never deployed.
# Build from the repo root: docker compose --profile app up --build
FROM python:3.12.7-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
RUN pip install --no-cache-dir --no-deps . && chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]
