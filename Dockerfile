# syntax=docker/dockerfile:1
# otfcc v0.10.4 only ships prebuilt linux/amd64 binaries
FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    OPENCC_WEB_HOST=0.0.0.0 \
    OPENCC_WEB_PORT=8000 \
    OPENCC_WEB_STORAGE_DIR=/data/jobs \
    OPENCC_WEB_MAX_FILE_MB=80 \
    OPENCC_WEB_MAX_TOTAL_UPLOAD_MB=240 \
    OPENCC_WEB_MAX_EXTRACTED_MB=320 \
    OPENCC_WEB_MAX_CONCURRENT_JOBS=2 \
    OPENCC_WEB_MAX_QUEUED_JOBS=20 \
    OPENCC_WEB_JOB_TTL_SECONDS=7200 \
    OPENCC_WEB_JOB_TIMEOUT_SECONDS=600 \
    OPENCC_WEB_RATE_LIMIT_PER_MIN=12 \
    OPENCC_WEB_TRUST_PROXY_HEADERS=false

WORKDIR /app

# Install otfcc v0.10.4 (otfccdump & otfccbuild) and clean up download tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && curl -fsSL -o /tmp/otfcc.zip "https://github.com/caryll/otfcc/releases/download/v0.10.4/otfcc-linux.x64-0.10.4.zip" \
    && mkdir -p /tmp/otfcc_bin \
    && unzip -q /tmp/otfcc.zip -d /tmp/otfcc_bin \
    && install -m 0755 /tmp/otfcc_bin/otfccdump /usr/local/bin/otfccdump \
    && install -m 0755 /tmp/otfcc_bin/otfccbuild /usr/local/bin/otfccbuild \
    && otfccdump --version \
    && rm -rf /tmp/otfcc.zip /tmp/otfcc_bin \
    && apt-get purge -y --auto-remove curl unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-web.txt setup.py setup.cfg README.md ./
RUN pip install --upgrade pip \
    && pip install setuptools \
    && pip install -r requirements.txt -r requirements-web.txt

COPY src ./src

# Download opencc-data 1.4.2 and prebuild OpenCC font lookup caches into the image
RUN python setup.py build

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --create-home appuser \
    && mkdir -p /data/jobs \
    && chown -R appuser:appgroup /app /data/jobs

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request, sys; r = urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4); sys.exit(0 if r.status == 200 else 1)"

CMD ["python", "-m", "OpenCCFontGenerator.web"]
