"""Configuration loaded from environment variables for the web/API service."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import tempfile
from typing import Tuple

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return max(minimum, int(raw.strip()))
    except ValueError:
        logger.warning('Invalid integer env %s=%r; falling back to default %s', name, raw, default)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


@dataclass(frozen=True)
class WebSettings:
    """Runtime settings and resource limits for the public Web/API server."""

    storage_dir: Path
    max_file_mb: int = 80
    max_total_upload_mb: int = 240
    max_extracted_mb: int = 320
    max_concurrent_jobs: int = 1
    max_concurrent_uploads: int = 4
    max_queued_jobs: int = 20
    min_free_disk_mb: int = 512
    job_ttl_seconds: int = 7200
    job_timeout_seconds: int = 600
    cleanup_interval_seconds: int = 60
    rate_limit_per_min: int = 12
    trust_proxy_headers: bool = False
    trusted_proxies: Tuple[str, ...] = ()
    cors_allow_origins: Tuple[str, ...] = ('*',)
    host: str = '0.0.0.0'
    port: int = 8000

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def max_total_upload_bytes(self) -> int:
        return self.max_total_upload_mb * 1024 * 1024

    @property
    def max_extracted_bytes(self) -> int:
        return self.max_extracted_mb * 1024 * 1024

    @property
    def min_free_disk_bytes(self) -> int:
        return self.min_free_disk_mb * 1024 * 1024

    @classmethod
    def from_env(cls) -> 'WebSettings':
        """Build WebSettings from OPENCC_WEB_* environment variables."""
        default_storage = Path(tempfile.gettempdir()) / 'opencc_font_jobs'
        storage_dir = Path(os.getenv('OPENCC_WEB_STORAGE_DIR', str(default_storage))).resolve()
        raw_origins = os.getenv('OPENCC_WEB_CORS_ORIGINS', '*')
        origins = tuple(o.strip() for o in raw_origins.split(',') if o.strip()) or ('*',)
        raw_proxies = os.getenv('OPENCC_WEB_TRUSTED_PROXIES', '')
        proxies = tuple(p.strip() for p in raw_proxies.split(',') if p.strip())
        return cls(
            storage_dir=storage_dir,
            max_file_mb=_env_int('OPENCC_WEB_MAX_FILE_MB', 80, minimum=1),
            max_total_upload_mb=_env_int('OPENCC_WEB_MAX_TOTAL_UPLOAD_MB', 240, minimum=1),
            max_extracted_mb=_env_int('OPENCC_WEB_MAX_EXTRACTED_MB', 320, minimum=1),
            max_concurrent_jobs=_env_int('OPENCC_WEB_MAX_CONCURRENT_JOBS', 1, minimum=1),
            max_concurrent_uploads=_env_int('OPENCC_WEB_MAX_CONCURRENT_UPLOADS', 4, minimum=1),
            max_queued_jobs=_env_int('OPENCC_WEB_MAX_QUEUED_JOBS', 20, minimum=1),
            min_free_disk_mb=_env_int('OPENCC_WEB_MIN_FREE_MB', 512, minimum=0),
            job_ttl_seconds=_env_int('OPENCC_WEB_JOB_TTL_SECONDS', 7200, minimum=60),
            job_timeout_seconds=_env_int('OPENCC_WEB_JOB_TIMEOUT_SECONDS', 600, minimum=30),
            cleanup_interval_seconds=_env_int('OPENCC_WEB_CLEANUP_INTERVAL_SECONDS', 60, minimum=10),
            rate_limit_per_min=_env_int('OPENCC_WEB_RATE_LIMIT_PER_MIN', 12, minimum=0),
            trust_proxy_headers=_env_bool('OPENCC_WEB_TRUST_PROXY_HEADERS', False),
            trusted_proxies=proxies,
            cors_allow_origins=origins,
            host=os.getenv('OPENCC_WEB_HOST', '0.0.0.0'),
            port=_env_int('OPENCC_WEB_PORT', 8000, minimum=1),
        )
