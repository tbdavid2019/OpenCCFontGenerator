"""CLI launcher for the OpenCCFontGenerator Web & API server."""

from __future__ import annotations

import uvicorn

from .config import WebSettings


def main() -> None:
    """Start Uvicorn using OPENCC_WEB_* environment settings."""
    settings = WebSettings.from_env()
    forwarded_ips = None
    if settings.trust_proxy_headers and settings.trusted_proxies:
        forwarded_ips = ','.join(settings.trusted_proxies)

    uvicorn.run(
        'OpenCCFontGenerator.web.app:app',
        host=settings.host,
        port=settings.port,
        proxy_headers=bool(forwarded_ips),
        forwarded_allow_ips=forwarded_ips,
        log_level='info',
    )


if __name__ == '__main__':
    main()
