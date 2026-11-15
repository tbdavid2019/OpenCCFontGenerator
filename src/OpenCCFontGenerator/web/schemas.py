"""Pydantic response schemas for OpenAPI documentation and type safety."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


JobMode = Literal['convert', 'rotate90', 'webfont', 'static-family', 'variable-family']
JobStatus = Literal['queued', 'running', 'completed', 'failed', 'cancelled']


class ArtifactInfo(BaseModel):
    """Metadata and download path for a single generated output file."""

    filename: str
    size_bytes: int
    kind: Literal['font', 'woff2', 'css', 'archive', 'other']
    primary: bool = False
    download_url: str


class JobResponse(BaseModel):
    """Job status payload returned on submission, polling, and batch queries."""

    job_id: str
    mode: JobMode
    status: JobStatus
    phase: str
    queue_position: int = 0
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    expires_at: str
    elapsed_seconds: Optional[float] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[ArtifactInfo] = Field(default_factory=list)
    download_url: Optional[str] = None
    log_tail: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Service readiness payload for container orchestrators and reverse proxies."""

    status: Literal['ok', 'degraded']
    opencc_data_version: Optional[str]
    cache_ready: bool
    otfccdump_available: bool
    otfccbuild_available: bool
    running_jobs: int
    queued_jobs: int


class SpecimenPair(BaseModel):
    """One before/after phrase sample showing how the active OpenCC config behaves."""

    source: str
    converted: str


class SpecimenPreviewResponse(BaseModel):
    """Live conversion preview calculated from compiled OpenCCFontGenerator cache tables."""

    config: str
    no_punc: bool
    sample_text: Optional[str] = None
    sample_converted: Optional[str] = None
    pairs: List[SpecimenPair]


class ServiceCapabilitiesResponse(BaseModel):
    """Public capability advertisement and current capacity snapshot."""

    service_version: str
    opencc_data_version: Optional[str]
    max_file_mb: int
    max_total_upload_mb: int
    max_extracted_mb: int
    max_concurrent_jobs: int
    max_queued_jobs: int
    rate_limit_per_min: int
    job_ttl_seconds: int
    running_jobs: int
    queued_jobs: int
    supported_extensions: List[str]
    archive_extensions: List[str]
    configs: List[str]
    merge_modes: List[str]
    fill_charsets: List[str]
    rotation_directions: List[str]
    variable_weights: List[str]
