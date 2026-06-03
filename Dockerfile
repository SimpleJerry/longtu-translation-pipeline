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
COPY pyproject.toml  /app/pyproject.toml

WORKDIR /app

# Install the project package so scripts can import it without sys.path injection (ADR-0039).
# --no-deps: runtime deps are already installed via requirements-serving.txt above;
# this only registers the src/ package in the Python environment.
RUN pip install --no-cache-dir --no-deps .

# Run as non-root user (uid 1000).
# Pre-create the HF Hub cache directory with correct ownership so that a named
# Docker volume mounted here is initialized with appuser permissions on first run
# (Docker copies image-dir contents into an empty named volume at mount time).
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /home/appuser/.cache
USER appuser

EXPOSE 8000

# start-period=600s covers the first-run ~2.3 GB HF model pull; warm cache cold start is ~35 s
HEALTHCHECK --interval=30s --timeout=10s --start-period=600s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "scripts/serve.py", "--config", "configs/serving/docker.json"]
