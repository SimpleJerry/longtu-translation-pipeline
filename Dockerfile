FROM python:3.12-slim

# curl is required for the HEALTHCHECK CMD
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install torch cu132 in its own layer so the ~2 GB wheel is cached independently
# of other serving dependencies. The cu132 wheel bundles the CUDA 13.2 runtime;
# no nvidia/cuda base image is needed (ADR-0035 sec 2).
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cu132 \
    torch==2.12.0+cu132

# Install remaining serving runtime dependencies (torch already satisfied above)
COPY requirements-serving.txt /tmp/requirements-serving.txt
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cu132 \
    -r /tmp/requirements-serving.txt

# Application code and static assets
# Model weights are NOT copied here — mounted as a read-only volume at runtime (ADR-0035 sec 5)
COPY src/            /app/src/
COPY scripts/        /app/scripts/
COPY configs/        /app/configs/
COPY data/glossary.csv /app/data/glossary.csv

WORKDIR /app

# Run as non-root user (uid 1000)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# start-period=90s covers the ~30 s cold start (torch + transformers import at first request)
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "scripts/serve.py", "--config", "configs/serving/docker.json"]
