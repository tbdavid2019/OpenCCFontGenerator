"""CLI launcher for the OpenCCFontGenerator Web & API server."""

from __future__ import annotations

import uvicorn

from .config import WebSettings


def main() -> None:
    """Start Uvicorn using OPENCC_WEB_* environment settings."""
    settings = WebSettings.from_env()

    # Keep Uvicorn proxy header rewriting disabled so _client_ip_from_scope in app.py
    # remains the single authoritative parser against the raw peer socket IP.
    # Run single-process (workers=1) because JobManager and rate limiter state are in-memory.
    uvicorn.run(
        'OpenCCFontGenerator.web.app:app',
        host=settings.host,
        port=settings.port,
        proxy_headers=False,
        forwarded_allow_ips=None,
        workers=1,
        log_level='info',
    )


if __name__ == '__main__':
    main()
