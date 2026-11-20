# syntax=docker/dockerfile:1
FROM debian:bookworm-slim AS otfcc-builder

ARG OTFCC_VERSION=0.10.4
ARG OTFCC_SHA256=d9c74825ddac700eb429de31de7cb0a249636f47c6a4cc64eaa102a40966cf00

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl clang binutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN set -eu \
    && curl -fsSL -o otfcc.tar.gz "https://github.com/caryll/otfcc/archive/refs/tags/v${OTFCC_VERSION}.tar.gz" \
    && echo "${OTFCC_SHA256}  otfcc.tar.gz" | sha256sum -c - \
    && tar -xzf otfcc.tar.gz \
    && cd "otfcc-${OTFCC_VERSION}" \
    && mkdir -p out \
    && export CFLAGS="-std=gnu11 -O2 -DNDEBUG -D_CARYLL_USE_PRE_SERIALIZED -DMAIN_VER=0 -DSECONDARY_VER=10 -DPATCH_VER=4 -fPIC -Wno-multichar -Wno-unused-const-variable" \
    && find dep/extern -name '*.c' | sort | nl -n rz -w 4 | xargs -n 2 -P "$(nproc)" sh -c 'clang $CFLAGS -Iinclude -Iinclude/dep -c "$2" -o "out/dep_${1}.o"' _ \
    && find lib -name '*.c' | sort | nl -n rz -w 4 | xargs -n 2 -P "$(nproc)" sh -c 'clang $CFLAGS -Iinclude -Ilib -c "$2" -o "out/lib_${1}.o"' _ \
    && clang $CFLAGS -Iinclude -Ilib -c src/stopwatch.c -o out/stopwatch.o \
    && clang $CFLAGS -Iinclude -Ilib -c src/otfccdump.c -o out/otfccdump.o \
    && clang $CFLAGS -Iinclude -Ilib -c src/otfccbuild.c -o out/otfccbuild.o \
    && ar rcs out/libotfcc.a out/dep_*.o out/lib_*.o \
    && clang -fPIC out/otfccdump.o out/stopwatch.o out/libotfcc.a -lm -o out/otfccdump \
    && clang -fPIC out/otfccbuild.o out/stopwatch.o out/libotfcc.a -lm -o out/otfccbuild \
    && strip out/otfccdump out/otfccbuild \
    && ./out/otfccdump --version \
    && ./out/otfccbuild --version \
    && install -d /out \
    && install -m 0755 out/otfccdump /out/otfccdump \
    && install -m 0755 out/otfccbuild /out/otfccbuild

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    TMPDIR=/data/tmp \
    OPENCC_WEB_HOST=0.0.0.0 \
    OPENCC_WEB_PORT=8000 \
    OPENCC_WEB_STORAGE_DIR=/data/jobs \
    OPENCC_WEB_MAX_FILE_MB=80 \
    OPENCC_WEB_MAX_TOTAL_UPLOAD_MB=240 \
    OPENCC_WEB_MAX_EXTRACTED_MB=320 \
    OPENCC_WEB_MAX_CONCURRENT_JOBS=1 \
    OPENCC_WEB_MAX_CONCURRENT_UPLOADS=4 \
    OPENCC_WEB_MAX_QUEUED_JOBS=20 \
    OPENCC_WEB_MIN_FREE_MB=512 \
    OPENCC_WEB_JOB_TTL_SECONDS=7200 \
    OPENCC_WEB_JOB_TIMEOUT_SECONDS=600 \
    OPENCC_WEB_RATE_LIMIT_PER_MIN=12 \
    OPENCC_WEB_TRUST_PROXY_HEADERS=false

WORKDIR /app

COPY --from=otfcc-builder /out/otfccdump /usr/local/bin/otfccdump
COPY --from=otfcc-builder /out/otfccbuild /usr/local/bin/otfccbuild
RUN otfccdump --version && otfccbuild --version

COPY requirements.txt requirements-web.txt setup.py setup.cfg README.md ./
RUN pip install --upgrade pip \
    && pip install setuptools \
    && pip install -r requirements.txt -r requirements-web.txt

COPY src ./src

# Download opencc-data 1.4.2 and prebuild OpenCC font lookup caches into the image
RUN python setup.py build && rm -rf /app/build

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --create-home appuser \
    && chown -R root:root /app \
    && chmod -R a+rX,go-w /app \
    && mkdir -p /data/jobs /data/tmp \
    && chown -R appuser:appgroup /data \
    && chmod 0750 /data /data/jobs /data/tmp

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request, sys; r = urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4); sys.exit(0 if r.status == 200 else 1)"

CMD ["python", "-m", "OpenCCFontGenerator.web"]
