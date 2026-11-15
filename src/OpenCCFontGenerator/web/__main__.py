"""CLI launcher for the OpenCCFontGenerator Web & API server."""

from __future__ import annotations

import uvicorn

from .config import WebSettings


def main() -> None:
    """Start Uvicorn using OPENCC_WEB_* environment settings."""
    settings = WebSettings.from_env()
    forwarded_ips = None
    if settings.trust_proxy_headers:
        forwarded_ips = ','.join(settings.trusted_proxies) if settings.trusted_proxies else '127.0.0.1'

    uvicorn.run(
        'OpenCCFontGenerator.web.app:app',
        host=settings.host,
        port=settings.port,
        proxy_headers=settings.trust_proxy_headers,
        forwarded_allow_ips=forwarded_ips,
        log_level='info',
    )


if __name__ == '__main__':
    main()
