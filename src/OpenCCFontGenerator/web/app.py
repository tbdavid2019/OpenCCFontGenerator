"""FastAPI application exposing the OpenCCFontGenerator Web UI and REST API."""

from __future__ import annotations

from contextlib import asynccontextmanager
import ipaddress
import json
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple, Union

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

import anyio
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..vf_family import WEIGHT_PRESETS
from .config import WebSettings
from .jobs import (
    ARCHIVE_EXTENSIONS,
    FONT_EXTENSIONS,
    JSON_EXTENSIONS,
    MAX_ARCHIVE_ENTRIES,
    ROTATE_EXTENSIONS,
    WEBFONT_EXTENSIONS,
    JobManager,
    ZipExtractionBudget,
    extract_fonts_from_zip,
    save_upload_file_checked,
)
from .preview import build_specimen_pairs, preview_convert
from .rate_limit import SlidingWindowRateLimiter
from .schemas import (
    HealthResponse,
    JobResponse,
    ServiceCapabilitiesResponse,
    SpecimenPreviewResponse,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / 'static'
SERVICE_VERSION = '1.0.0'
MULTIPART_OVERHEAD_BYTES = 4 * 1024 * 1024  # Bound headers, form fields, and MIME boundaries

ConfigChoice = Literal['s2t', 'twp', 's2tw', 's2hk', 't2s']
MergeModeChoice = Literal['opencc', 'universal']
FillCharsetChoice = Literal['none', 'hant-common', 'opencc-hant', 'han']
DirectionChoice = Literal['ccw', 'cw']
VALID_WEIGHT_NAMES = [preset[0] for preset in WEIGHT_PRESETS]
SAFE_PREFIX_RE = re.compile(r'^[A-Za-z0-9._-]+$')


class _BodyTooLarge(Exception):
    """Internal control-flow error raised when streaming upload exceeds hard ingress limit."""


def _parse_trusted_networks(entries: Tuple[str, ...]) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
    for raw in entries:
        cleaned = raw.strip()
        if not cleaned:
            continue
        try:
            networks.append(ipaddress.ip_network(cleaned, strict=False))
        except ValueError as exc:
            raise ValueError(f'無效的 OPENCC_WEB_TRUSTED_PROXIES 項目：{cleaned!r}') from exc
    return networks


def _is_trusted_ip(ip_str: str, networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]) -> bool:
    if not networks:
        return False
    try:
        addr = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return False
    return any(addr in net for net in networks)


def _client_ip_from_scope(
    scope: Dict[str, Any],
    trust_proxy: bool,
    trusted_networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]],
) -> str:
    client = scope.get('client')
    peer_host = client[0] if client else 'unknown'
    # Fail closed unless proxy trust is explicitly enabled AND non-empty trusted proxies are configured
    if not trust_proxy or not trusted_networks or not _is_trusted_ip(peer_host, trusted_networks):
        return peer_host

    headers: Dict[bytes, bytes] = dict(scope.get('headers') or [])
    raw_xff = headers.get(b'x-forwarded-for')
    if raw_xff:
        hops = [h.strip() for h in raw_xff.decode('latin-1').split(',') if h.strip()]
        if hops:
            for hop in reversed(hops):
                if not _is_trusted_ip(hop, trusted_networks):
                    return hop
            return hops[0]

    raw_xri = headers.get(b'x-real-ip')
    if raw_xri:
        return raw_xri.decode('latin-1').strip() or peer_host

    return peer_host


async def _send_json_error(
    send: Callable[[Dict[str, Any]], Any],
    status_code: int,
    detail: str,
    headers: Optional[Dict[str, str]] = None,
) -> None:
    payload = json.dumps({'detail': detail}, ensure_ascii=False).encode('utf-8')
    raw_headers: List[Tuple[bytes, bytes]] = [
        (b'content-type', b'application/json; charset=utf-8'),
        (b'content-length', str(len(payload)).encode('ascii')),
    ]
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode('latin-1'), v.encode('latin-1')))
    await send({'type': 'http.response.start', 'status': status_code, 'headers': raw_headers})
    await send({'type': 'http.response.body', 'body': payload})


class UploadGuardMiddleware:
    """Pure ASGI middleware enforcing per-IP rate limit and max body size before multipart parsing."""

    def __init__(
        self,
        app: Any,
        settings: WebSettings,
        limiter: SlidingWindowRateLimiter,
    ) -> None:
        self.app = app
        self.settings = settings
        self.limiter = limiter
        self.max_body_bytes = settings.max_total_upload_bytes + MULTIPART_OVERHEAD_BYTES
        self.trusted_networks = _parse_trusted_networks(settings.trusted_proxies)

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope.get('type') != 'http'
            or scope.get('method') != 'POST'
            or not str(scope.get('path', '')).startswith('/api/v1/jobs/')
        ):
            await self.app(scope, receive, send)
            return

        ip = _client_ip_from_scope(scope, self.settings.trust_proxy_headers, self.trusted_networks)
        res = self.limiter.check_and_record(ip)
        if not res.allowed:
            await _send_json_error(
                send,
                status_code=429,
                detail=f'請求過於頻繁（每分鐘上限 {res.limit} 次任務），請於 {res.retry_after} 秒後再試。',
                headers={'Retry-After': str(res.retry_after)},
            )
            return

        headers = dict(scope.get('headers') or [])
        raw_cl = headers.get(b'content-length')
        if raw_cl is not None:
            try:
                content_length = int(raw_cl.decode('ascii').strip())
            except ValueError:
                await _send_json_error(send, status_code=400, detail='無效的 Content-Length 標頭。')
                return
            if content_length > self.max_body_bytes:
                await _send_json_error(
                    send,
                    status_code=413,
                    detail=f'請求內容超過單次上傳上限（{self.settings.max_total_upload_mb} MB）。',
                )
                return

        received_bytes = 0
        body_exceeded = False
        response_started = False

        async def bounded_receive() -> Dict[str, Any]:
            nonlocal received_bytes, body_exceeded
            message = await receive()
            if message.get('type') == 'http.request':
                received_bytes += len(message.get('body', b''))
                if received_bytes > self.max_body_bytes:
                    body_exceeded = True
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message: Dict[str, Any]) -> None:
            nonlocal response_started
            if body_exceeded and not response_started:
                return
            if message.get('type') == 'http.response.start':
                response_started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, tracking_send)
        except _BodyTooLarge:
            body_exceeded = True

        if body_exceeded and not response_started:
            await _send_json_error(
                send,
                status_code=413,
                detail=f'請求內容超過單次上傳上限（{self.settings.max_total_upload_mb} MB）。',
            )


def _read_opencc_data_version() -> Optional[str]:
    ver_file = PACKAGE_ROOT / 'opencc_data' / '.opencc_data_version'
    if ver_file.exists():
        return ver_file.read_text(encoding='utf-8').strip() or None
    return None


def _is_cache_ready() -> bool:
    required = (
        PACKAGE_ROOT / 'cache' / 'convert_table_chars.txt',
        PACKAGE_ROOT / 'cache' / 'convert_table_chars_twp.txt',
        PACKAGE_ROOT / 'cache' / 'code_points_han.txt',
    )
    return all(p.is_file() for p in required)


def _validate_safe_prefix(value: Optional[str], label: str) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if '..' in cleaned or not SAFE_PREFIX_RE.fullmatch(cleaned):
        raise HTTPException(
            status_code=400,
            detail=f'{label} 僅允許英數字與 . _ - 字元，不可包含路徑或 ..。',
        )
    return cleaned


async def _ingest_font_collection(
    uploads: List[UploadFile],
    target_dir: Path,
    allowed_font_exts: Set[str],
    label: str,
    max_file_bytes: int,
    remaining_bytes: int,
    extraction_budget: ZipExtractionBudget,
) -> Tuple[List[Path], int]:
    """Save uploaded font files or ZIP archives into target_dir using a shared extraction budget."""
    combined_exts = allowed_font_exts | ARCHIVE_EXTENSIONS
    saved_fonts: List[Path] = []
    consumed = 0

    for upload in uploads:
        if not upload.filename:
            continue
        temp_archive_dir = target_dir / '_archives'
        is_zip = Path(upload.filename).suffix.lower() == '.zip'
        save_dest = temp_archive_dir if is_zip else target_dir
        saved_path, size = await save_upload_file_checked(
            upload,
            save_dest,
            combined_exts,
            label,
            max_file_bytes,
            remaining_bytes - consumed,
        )
        consumed += size
        if is_zip:
            try:
                extracted = await anyio.to_thread.run_sync(
                    extract_fonts_from_zip,
                    saved_path,
                    target_dir,
                    allowed_font_exts,
                    extraction_budget.remaining_bytes,
                    extraction_budget,
                )
            finally:
                saved_path.unlink(missing_ok=True)
            saved_fonts.extend(extracted)
        else:
            saved_fonts.append(saved_path)

    return saved_fonts, consumed


def create_app(settings: Optional[WebSettings] = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    cfg = settings or WebSettings.from_env()
    manager = JobManager(cfg)
    limiter = SlidingWindowRateLimiter(cfg.rate_limit_per_min)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        manager.start()
        try:
            yield
        finally:
            manager.shutdown()

    application = FastAPI(
        title='OpenCCFontGenerator Web & API',
        version=SERVICE_VERSION,
        description=(
            '非同步 OpenType CJK 字型簡繁轉換、GSUB 詞彙編譯、90° 直排旋轉、'
            'WOFF2 Webfont 打包與多字重家族批次生成服務。'
        ),
        lifespan=lifespan,
    )

    application.state.settings = cfg
    application.state.job_manager = manager
    application.state.rate_limiter = limiter

    # Guard runs inside CORS so 413/429 responses still carry CORS headers while running before multipart parsing
    application.add_middleware(UploadGuardMiddleware, settings=cfg, limiter=limiter)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_allow_origins),
        allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'],
        allow_headers=['*'],
    )

    if STATIC_DIR.is_dir():
        application.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

    @application.get('/', include_in_schema=False)
    def serve_index():
        index_path = STATIC_DIR / 'index.html'
        if not index_path.is_file():
            raise HTTPException(status_code=404, detail='Web UI 靜態檔案尚未建置。')
        return FileResponse(index_path)

    @application.get('/healthz', response_model=HealthResponse, tags=['System'])
    def healthz():
        dump_ok = shutil.which('otfccdump') is not None
        build_ok = shutil.which('otfccbuild') is not None
        cache_ok = _is_cache_ready()
        running, queued = manager.counts()
        status = 'ok' if (dump_ok and build_ok and cache_ok) else 'degraded'
        payload = HealthResponse(
            status=status,
            opencc_data_version=_read_opencc_data_version(),
            cache_ready=cache_ok,
            otfccdump_available=dump_ok,
            otfccbuild_available=build_ok,
            running_jobs=running,
            queued_jobs=queued,
        )
        if status != 'ok':
            content = payload.model_dump() if hasattr(payload, 'model_dump') else payload.dict()
            return JSONResponse(status_code=503, content=content)
        return payload

    @application.get('/api/v1/capabilities', response_model=ServiceCapabilitiesResponse, tags=['System'])
    def get_capabilities():
        running, queued = manager.counts()
        return ServiceCapabilitiesResponse(
            service_version=SERVICE_VERSION,
            opencc_data_version=_read_opencc_data_version(),
            max_file_mb=cfg.max_file_mb,
            max_total_upload_mb=cfg.max_total_upload_mb,
            max_extracted_mb=cfg.max_extracted_mb,
            max_concurrent_jobs=cfg.max_concurrent_jobs,
            max_queued_jobs=cfg.max_queued_jobs,
            rate_limit_per_min=cfg.rate_limit_per_min,
            job_ttl_seconds=cfg.job_ttl_seconds,
            running_jobs=running,
            queued_jobs=queued,
            supported_extensions=sorted(FONT_EXTENSIONS),
            archive_extensions=sorted(ARCHIVE_EXTENSIONS),
            configs=['s2t', 'twp', 's2tw', 's2hk', 't2s'],
            merge_modes=['opencc', 'universal'],
            fill_charsets=['none', 'hant-common', 'opencc-hant', 'han'],
            rotation_directions=['ccw', 'cw'],
            variable_weights=VALID_WEIGHT_NAMES,
        )

    @application.get('/api/v1/preview', response_model=SpecimenPreviewResponse, tags=['Preview'])
    def get_specimen_preview(
        config: ConfigChoice = 's2t',
        no_punc: bool = False,
        text: Annotated[Optional[str], Query(max_length=120)] = None,
    ):
        pairs = build_specimen_pairs(config=config, no_punc=no_punc)
        sample_converted = preview_convert(text, config=config, no_punc=no_punc) if text else None
        return SpecimenPreviewResponse(
            config=config,
            no_punc=no_punc,
            sample_text=text,
            sample_converted=sample_converted,
            pairs=pairs,
        )

    @application.post(
        '/api/v1/jobs/convert',
        response_model=JobResponse,
        status_code=202,
        tags=['Jobs'],
    )
    async def submit_convert_job(
        source_font: Annotated[UploadFile, File(description='來源字型檔 (.ttf / .otf / .ttc / .woff2)')],
        fallback_font: Annotated[Optional[UploadFile], File(description='選填備用字型檔 (.ttf / .otf / .ttc / .woff2)')] = None,
        name_header_file: Annotated[Optional[UploadFile], File(description='選填進階字型名稱 JSON 設定檔')] = None,
        config: Annotated[ConfigChoice, Form()] = 's2t',
        font_name: Annotated[Optional[str], Form(max_length=120)] = None,
        font_version: Annotated[Optional[float], Form()] = None,
        ttc_index: Annotated[Optional[int], Form(ge=0)] = None,
        merge_mode: Annotated[MergeModeChoice, Form()] = 'opencc',
        fill_charset: Annotated[FillCharsetChoice, Form()] = 'none',
        no_punc: Annotated[bool, Form()] = False,
        force_vertical: Annotated[bool, Form()] = False,
        output_woff2: Annotated[bool, Form()] = False,
        kobo_mode: Annotated[bool, Form()] = False,
    ):
        job_id, job_dir = manager.create_job_dir()
        inputs_dir = job_dir / 'inputs'
        try:
            remaining = cfg.max_total_upload_bytes
            src_path, src_bytes = await save_upload_file_checked(
                source_font, inputs_dir / 'source', FONT_EXTENSIONS, '來源字型', cfg.max_file_bytes, remaining,
            )
            remaining -= src_bytes

            fb_path = None
            if fallback_font and fallback_font.filename:
                fb_path, fb_bytes = await save_upload_file_checked(
                    fallback_font, inputs_dir / 'fallback', FONT_EXTENSIONS, '備用字型', cfg.max_file_bytes, remaining,
                )
                remaining -= fb_bytes

            nh_path = None
            if name_header_file and name_header_file.filename:
                nh_path, _ = await save_upload_file_checked(
                    name_header_file, inputs_dir / 'meta', JSON_EXTENSIONS, '名稱 JSON 設定檔', 2 * 1024 * 1024, remaining,
                )

            effective_fill = fill_charset if fb_path else 'none'
            spec = {
                'input_file': str(src_path),
                'fallback_font': str(fb_path) if fb_path else None,
                'name_header_file': str(nh_path) if nh_path else None,
                'params': {
                    'config': config,
                    'font_name': font_name.strip() if font_name and font_name.strip() else None,
                    'font_version': font_version,
                    'ttc_index': ttc_index,
                    'merge_mode': merge_mode,
                    'fill_charset': effective_fill,
                    'no_punc': no_punc,
                    'force_vertical': force_vertical,
                    'output_woff2': output_woff2,
                    'kobo_mode': kobo_mode,
                },
            }
            summary = {
                'source_filename': src_path.name,
                'fallback_filename': fb_path.name if fb_path else None,
                'config': config,
                'no_punc': no_punc,
                'force_vertical': force_vertical,
                'output_woff2': output_woff2,
                'kobo_mode': kobo_mode,
            }
            return manager.submit_job(job_id, 'convert', spec, summary)
        except BaseException:
            manager.release_pending_job(job_id)
            raise

    @application.post(
        '/api/v1/jobs/rotate90',
        response_model=JobResponse,
        status_code=202,
        tags=['Jobs'],
    )
    async def submit_rotate90_job(
        source_font: Annotated[UploadFile, File(description='來源字型檔 (.ttf / .otf / .ttc)')],
        direction: Annotated[DirectionChoice, Form()] = 'ccw',
        rotate_all: Annotated[bool, Form()] = False,
        ttc_index: Annotated[Optional[int], Form(ge=0)] = None,
        kobo_mode: Annotated[bool, Form()] = False,
    ):
        job_id, job_dir = manager.create_job_dir()
        inputs_dir = job_dir / 'inputs'
        try:
            src_path, _ = await save_upload_file_checked(
                source_font, inputs_dir / 'source', ROTATE_EXTENSIONS, '來源字型', cfg.max_file_bytes, cfg.max_total_upload_bytes,
            )
            spec = {
                'input_file': str(src_path),
                'params': {
                    'direction': direction,
                    'rotate_all': rotate_all,
                    'ttc_index': ttc_index,
                    'kobo_mode': kobo_mode,
                },
            }
            summary = {
                'source_filename': src_path.name,
                'direction': direction,
                'rotate_all': rotate_all,
                'kobo_mode': kobo_mode,
            }
            return manager.submit_job(job_id, 'rotate90', spec, summary)
        except BaseException:
            manager.release_pending_job(job_id)
            raise

    @application.post(
        '/api/v1/jobs/webfont',
        response_model=JobResponse,
        status_code=202,
        tags=['Jobs'],
    )
    async def submit_webfont_job(
        source_font: Annotated[UploadFile, File(description='來源字型檔 (.ttf / .otf)')],
        font_family: Annotated[Optional[str], Form(max_length=120)] = None,
    ):
        job_id, job_dir = manager.create_job_dir()
        inputs_dir = job_dir / 'inputs'
        try:
            src_path, _ = await save_upload_file_checked(
                source_font, inputs_dir / 'source', WEBFONT_EXTENSIONS, '來源字型', cfg.max_file_bytes, cfg.max_total_upload_bytes,
            )
            spec = {
                'input_file': str(src_path),
                'params': {
                    'font_family': font_family.strip() if font_family and font_family.strip() else None,
                },
            }
            summary = {
                'source_filename': src_path.name,
                'font_family': spec['params']['font_family'] or src_path.stem,
            }
            return manager.submit_job(job_id, 'webfont', spec, summary)
        except BaseException:
            manager.release_pending_job(job_id)
            raise

    @application.post(
        '/api/v1/jobs/static-family',
        response_model=JobResponse,
        status_code=202,
        tags=['Jobs'],
    )
    async def submit_static_family_job(
        source_files: Annotated[List[UploadFile], File(description='多字重來源字型檔（支援多檔或 .zip 壓縮包）')],
        fallback_files: Annotated[Optional[List[UploadFile]], File(description='選填備用字型群（支援多檔或 .zip 壓縮包）')] = None,
        fallback_prefix: Annotated[Optional[str], Form(max_length=80)] = None,
        config: Annotated[ConfigChoice, Form()] = 's2t',
        merge_mode: Annotated[MergeModeChoice, Form()] = 'universal',
        fill_charset: Annotated[FillCharsetChoice, Form()] = 'hant-common',
        no_punc: Annotated[bool, Form()] = False,
        force_vertical: Annotated[bool, Form()] = False,
        output_woff2: Annotated[bool, Form()] = False,
        family_name_prefix: Annotated[Optional[str], Form(max_length=100)] = None,
        kobo_mode: Annotated[bool, Form()] = False,
    ):
        clean_prefix = _validate_safe_prefix(fallback_prefix, 'fallback_prefix')
        job_id, job_dir = manager.create_job_dir()
        inputs_dir = job_dir / 'inputs'
        source_dir = inputs_dir / 'source'
        fallback_dir = inputs_dir / 'fallback'
        try:
            remaining = cfg.max_total_upload_bytes
            budget = ZipExtractionBudget(
                remaining_bytes=cfg.max_extracted_bytes,
                remaining_entries=MAX_ARCHIVE_ENTRIES,
                max_single_file_bytes=cfg.max_file_bytes,
            )
            src_list, src_bytes = await _ingest_font_collection(
                source_files, source_dir, FONT_EXTENSIONS, '來源字型', cfg.max_file_bytes, remaining, budget,
            )
            if not src_list:
                raise HTTPException(status_code=400, detail='請至少上傳一個有效的來源字型檔或包含字型的 ZIP。')
            remaining -= src_bytes

            fb_list: List[Path] = []
            if fallback_files:
                fb_list, _ = await _ingest_font_collection(
                    fallback_files, fallback_dir, FONT_EXTENSIONS, '備用字型', cfg.max_file_bytes, remaining, budget,
                )

            spec = {
                'input_dir': str(source_dir),
                'fallback_dir': str(fallback_dir) if fb_list else None,
                'params': {
                    'fallback_prefix': clean_prefix,
                    'config': config,
                    'merge_mode': merge_mode,
                    'fill_charset': fill_charset if fb_list else 'none',
                    'no_punc': no_punc,
                    'force_vertical': force_vertical,
                    'output_woff2': output_woff2,
                    'family_name_prefix': family_name_prefix.strip() if family_name_prefix and family_name_prefix.strip() else None,
                    'kobo_mode': kobo_mode,
                },
            }
            summary = {
                'source_count': len(src_list),
                'fallback_count': len(fb_list),
                'config': config,
                'family_name_prefix': spec['params']['family_name_prefix'],
                'output_woff2': output_woff2,
            }
            return manager.submit_job(job_id, 'static-family', spec, summary)
        except BaseException:
            manager.release_pending_job(job_id)
            raise

    @application.post(
        '/api/v1/jobs/variable-family',
        response_model=JobResponse,
        status_code=202,
        tags=['Jobs'],
    )
    async def submit_variable_family_job(
        source_font: Annotated[UploadFile, File(description='可變字型主檔（需含 fvar / wght 軸）')],
        fallback_files: Annotated[List[UploadFile], File(description='對應字重備用字型群（多檔或 .zip，例如 NotoSansTC-Regular.ttf）')],
        fallback_prefix: Annotated[str, Form(max_length=80)] = 'NotoSansTC',
        config: Annotated[ConfigChoice, Form()] = 's2t',
        weights: Annotated[Optional[str], Form(description='逗號分隔字重，例如 Regular,Medium,Bold；留空則產生全部 9 種字重')] = None,
        output_woff2: Annotated[bool, Form()] = False,
        family_name_prefix: Annotated[Optional[str], Form(max_length=100)] = None,
        kobo_mode: Annotated[bool, Form()] = False,
    ):
        clean_prefix = _validate_safe_prefix(fallback_prefix, 'fallback_prefix') or 'NotoSansTC'
        selected_weights = None
        if weights and weights.strip():
            parsed = [w.strip() for w in weights.split(',') if w.strip()]
            invalid = [w for w in parsed if w not in VALID_WEIGHT_NAMES]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f'無效的字重名稱：{", ".join(invalid)}；可選：{", ".join(VALID_WEIGHT_NAMES)}',
                )
            selected_weights = parsed

        job_id, job_dir = manager.create_job_dir()
        inputs_dir = job_dir / 'inputs'
        fallback_dir = inputs_dir / 'fallback'
        try:
            remaining = cfg.max_total_upload_bytes
            budget = ZipExtractionBudget(
                remaining_bytes=cfg.max_extracted_bytes,
                remaining_entries=MAX_ARCHIVE_ENTRIES,
                max_single_file_bytes=cfg.max_file_bytes,
            )
            src_path, src_bytes = await save_upload_file_checked(
                source_font, inputs_dir / 'source', WEBFONT_EXTENSIONS, '可變字型主檔', cfg.max_file_bytes, remaining,
            )
            remaining -= src_bytes

            fb_list, _ = await _ingest_font_collection(
                fallback_files, fallback_dir, WEBFONT_EXTENSIONS, '備用字型', cfg.max_file_bytes, remaining, budget,
            )
            if not fb_list:
                raise HTTPException(status_code=400, detail='可變字型家族模式必須提供至少一個對應字重的備用字型檔。')

            spec = {
                'input_file': str(src_path),
                'fallback_dir': str(fallback_dir),
                'params': {
                    'fallback_prefix': clean_prefix,
                    'config': config,
                    'weights': selected_weights,
                    'output_woff2': output_woff2,
                    'family_name_prefix': family_name_prefix.strip() if family_name_prefix and family_name_prefix.strip() else None,
                    'kobo_mode': kobo_mode,
                },
            }
            summary = {
                'source_filename': src_path.name,
                'fallback_count': len(fb_list),
                'fallback_prefix': spec['params']['fallback_prefix'],
                'weights': selected_weights or VALID_WEIGHT_NAMES,
                'config': config,
            }
            return manager.submit_job(job_id, 'variable-family', spec, summary)
        except BaseException:
            manager.release_pending_job(job_id)
            raise

    @application.get('/api/v1/jobs', response_model=List[JobResponse], tags=['Jobs'])
    def query_jobs(ids: Annotated[Optional[str], Query(description='以逗號分隔要查詢的 job_id（最多 30 筆）')] = None):
        if not ids:
            return []
        job_ids = [item.strip() for item in ids.split(',') if item.strip()][:30]
        results = []
        for job_id in job_ids:
            job = manager.get_job(job_id)
            if job is not None:
                results.append(job)
        return results

    @application.get('/api/v1/jobs/{job_id}', response_model=JobResponse, tags=['Jobs'])
    def get_job_status(job_id: str):
        job = manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail='找不到指定的任務 ID 或任務已過期清除。')
        return job

    @application.get('/api/v1/jobs/{job_id}/download', tags=['Jobs'])
    def download_primary_artifact(job_id: str):
        file_path, filename = manager.get_artifact_path(job_id)
        return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')

    @application.get('/api/v1/jobs/{job_id}/artifacts/{filename}', tags=['Jobs'])
    def download_specific_artifact(job_id: str, filename: str):
        file_path, resolved_name = manager.get_artifact_path(job_id, filename=filename)
        return FileResponse(path=file_path, filename=resolved_name, media_type='application/octet-stream')

    @application.delete('/api/v1/jobs/{job_id}', tags=['Jobs'])
    def delete_or_cancel_job(job_id: str):
        removed = manager.delete_job(job_id)
        if not removed:
            raise HTTPException(status_code=404, detail='找不到指定的任務 ID 或任務已清除。')
        return {'deleted': True, 'job_id': job_id}

    return application


app = create_app()
