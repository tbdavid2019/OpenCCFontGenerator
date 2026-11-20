"""Async job manager, safe upload/archive handling, worker execution, and TTL cleanup."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time
from typing import Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import quote
import uuid
import zipfile
import zlib

from fastapi import HTTPException, UploadFile

from .config import WebSettings


FONT_EXTENSIONS = {'.ttf', '.otf', '.ttc', '.woff2'}
ROTATE_EXTENSIONS = {'.ttf', '.otf', '.ttc'}
WEBFONT_EXTENSIONS = {'.ttf', '.otf'}
ARCHIVE_EXTENSIONS = {'.zip'}
JSON_EXTENSIONS = {'.json'}

MAX_ARCHIVE_ENTRIES = 64
MAX_ZIP_CD_BYTES = 4 * 1024 * 1024
ALLOWED_ZIP_COMPRESSIONS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
MAX_FILENAME_BYTES = 180
MAX_UNIQUE_NAME_ATTEMPTS = 100
MAX_LOG_READ_BYTES = 32 * 1024
ORPHAN_INGESTION_AGE_SECONDS = 900
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MiB
JOB_ID_RE = re.compile(r'^[a-f0-9]{12,32}$')


@dataclass
class ZipExtractionBudget:
    """Shared uncompressed byte and entry budget across archives in one request."""

    remaining_bytes: int
    remaining_entries: int = MAX_ARCHIVE_ENTRIES
    max_single_file_bytes: int = 80 * 1024 * 1024


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


def is_within_dir(child: Path, parent: Path) -> bool:
    """Python 3.8+ safe check that child resolves inside parent directory."""
    try:
        return os.path.commonpath([str(child.resolve()), str(parent.resolve())]) == str(parent.resolve())
    except ValueError:
        return False


def _next_unique_path(dest_dir: Path, filename: str) -> Path:
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    target = dest_dir / filename
    counter = 1
    while target.exists():
        if counter > MAX_UNIQUE_NAME_ATTEMPTS:
            return dest_dir / f'{stem}_{uuid.uuid4().hex[:6]}{suffix}'
        target = dest_dir / f'{stem}_{counter}{suffix}'
        counter += 1
    return target


def _truncate_utf8_bytes(text: str, max_bytes: int) -> str:
    if max_bytes <= 0 or not text:
        return ''
    encoded = text.encode('utf-8')
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode('utf-8', errors='ignore')


def sanitize_filename(filename: Optional[str], fallback: str = 'font.ttf') -> str:
    """Strip directory paths and unsafe characters while keeping extension and UTF-8 byte cap intact."""
    base = Path(filename or fallback).name
    raw_stem = Path(base).stem
    raw_suffix = Path(base).suffix
    clean_suffix = re.sub(r'[^A-Za-z0-9.]+', '', raw_suffix)[:16]
    clean_stem = re.sub(r'[^A-Za-z0-9._()\-\u4e00-\u9fff]+', '_', raw_stem).strip('._')
    if not clean_stem:
        clean_stem = Path(fallback).stem or 'file'
    suffix_bytes = len(clean_suffix.encode('utf-8'))
    max_stem_bytes = max(1, MAX_FILENAME_BYTES - suffix_bytes)
    truncated_stem = _truncate_utf8_bytes(clean_stem, max_stem_bytes).strip('._')
    if not truncated_stem:
        truncated_stem = _truncate_utf8_bytes(Path(fallback).stem or 'file', max_stem_bytes) or 'file'
    result = f'{truncated_stem}{clean_suffix}'
    if result.startswith('.'):
        result = f'_{result.lstrip(".")}'
    return result or fallback


def validate_extension(filename: str, allowed_extensions: Set[str], label: str) -> str:
    """Validate and return lowercase file extension."""
    ext = Path(filename).suffix.lower()
    if ext not in allowed_extensions:
        allowed_text = ', '.join(sorted(allowed_extensions))
        raise HTTPException(
            status_code=400,
            detail=f'{label} 格式不支援（{ext or "無副檔名"}），僅支援：{allowed_text}',
        )
    return ext


async def save_upload_file_checked(
    upload: UploadFile,
    dest_dir: Path,
    allowed_extensions: Set[str],
    label: str,
    max_file_bytes: int,
    remaining_total_bytes: int,
) -> Tuple[Path, int]:
    """Stream an UploadFile to disk while enforcing extension and byte limits."""
    safe_name = sanitize_filename(upload.filename, fallback=f'{label}.bin')
    validate_extension(safe_name, allowed_extensions, label)

    dest_dir.mkdir(parents=True, exist_ok=True)
    target = _next_unique_path(dest_dir, safe_name)

    written = 0
    try:
        with target.open('wb') as out:
            while True:
                chunk = await upload.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                next_written = written + len(chunk)
                if next_written > max_file_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f'{label}「{safe_name}」超過單檔上限（{max_file_bytes // (1024 * 1024)} MB）。',
                    )
                if next_written > remaining_total_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail='本次上傳檔案總容量超過伺服器單次請求上限。',
                    )
                out.write(chunk)
                written = next_written
    except (Exception, asyncio.CancelledError):
        if target.exists():
            target.unlink()
        raise
    finally:
        await upload.close()

    if written == 0:
        if target.exists():
            target.unlink()
        raise HTTPException(status_code=400, detail=f'{label}「{safe_name}」是空檔案。')

    return target, written


def _validate_zip_eocd_and_cd(zip_path: Path, max_entries: int, max_cd_bytes: int = MAX_ZIP_CD_BYTES) -> None:
    """Inspect ZIP End-of-Central-Directory metadata before zipfile parses central directory records."""
    try:
        with zip_path.open('rb') as fp:
            fp.seek(0, os.SEEK_END)
            file_size = fp.tell()
            if file_size < 22:
                raise HTTPException(status_code=400, detail='上傳的 ZIP 壓縮檔格式損毀或無效。')

            read_len = min(file_size, 65557)
            tail_offset = file_size - read_len
            fp.seek(tail_offset)
            tail = fp.read(read_len)

            eocd_rel = tail.rfind(b'PK\x05\x06')
            if eocd_rel < 0 or (eocd_rel + 22) > len(tail):
                raise HTTPException(status_code=400, detail='上傳的 ZIP 壓縮檔格式損毀或無效。')

            _, _, _, _, total_entries, cd_size, cd_offset, comment_len = struct.unpack(
                '<4sHHHHIIH',
                tail[eocd_rel:eocd_rel + 22],
            )
            eocd_abs = tail_offset + eocd_rel
            if eocd_abs + 22 + comment_len > file_size:
                raise HTTPException(status_code=400, detail='上傳的 ZIP 壓縮檔結構無效。')

            if total_entries == 0xFFFF or cd_size == 0xFFFFFFFF or cd_offset == 0xFFFFFFFF:
                if eocd_abs < 20:
                    raise HTTPException(status_code=400, detail='上傳的 ZIP64 壓縮檔結構無效。')
                fp.seek(eocd_abs - 20)
                loc = fp.read(20)
                if len(loc) != 20 or not loc.startswith(b'PK\x06\x07'):
                    raise HTTPException(status_code=400, detail='上傳的 ZIP64 壓縮檔結構無效。')
                _, _, z64_offset, _ = struct.unpack('<4sIQI', loc)
                if z64_offset + 56 > eocd_abs - 20:
                    raise HTTPException(status_code=400, detail='上傳的 ZIP64 壓縮檔結構無效。')
                fp.seek(z64_offset)
                z64 = fp.read(56)
                if len(z64) != 56 or not z64.startswith(b'PK\x06\x06'):
                    raise HTTPException(status_code=400, detail='上傳的 ZIP64 壓縮檔結構無效。')
                _, _, _, _, _, _, _, total_entries, cd_size, cd_offset = struct.unpack('<4sQHHIIQQQQ', z64)

            if total_entries > max_entries:
                raise HTTPException(
                    status_code=400,
                    detail=f'壓縮檔內項目數量過多（單次請求最多 {MAX_ARCHIVE_ENTRIES} 個）。',
                )
            if cd_size > max_cd_bytes or cd_offset + cd_size > eocd_abs:
                raise HTTPException(status_code=400, detail='壓縮檔中央目錄異常或過大，拒絕解壓。')
    except HTTPException:
        raise
    except OSError as exc:
        raise HTTPException(status_code=400, detail='無法讀取上傳的 ZIP 壓縮檔。') from exc


def extract_fonts_from_zip(
    zip_path: Path,
    dest_dir: Path,
    allowed_extensions: Set[str],
    max_total_uncompressed_bytes: int,
    budget: Optional[ZipExtractionBudget] = None,
) -> List[Path]:
    """Safely extract allowed font files from a ZIP archive with Zip-Slip and bomb guards."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    active_budget = budget or ZipExtractionBudget(
        remaining_bytes=max_total_uncompressed_bytes,
        remaining_entries=MAX_ARCHIVE_ENTRIES,
        max_single_file_bytes=max_total_uncompressed_bytes,
    )
    _validate_zip_eocd_and_cd(zip_path, active_budget.remaining_entries)
    extracted: List[Path] = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            all_infos = zf.infolist()
            if len(all_infos) > active_budget.remaining_entries:
                raise HTTPException(
                    status_code=400,
                    detail=f'壓縮檔內項目數量過多（單次請求最多 {MAX_ARCHIVE_ENTRIES} 個）。',
                )
            active_budget.remaining_entries -= len(all_infos)

            for info in all_infos:
                raw_name = info.filename.replace('\\', '/')
                posix_path = PurePosixPath(raw_name)
                if not posix_path.parts or raw_name.startswith('/') or '..' in posix_path.parts or ':' in posix_path.parts[0]:
                    raise HTTPException(status_code=400, detail='壓縮檔包含不安全的路徑。')

                if info.is_dir():
                    continue
                # Skip macOS metadata and hidden entries
                if '__MACOSX' in posix_path.parts or posix_path.name.startswith('.'):
                    continue
                # Reject POSIX symlinks
                if info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000:
                    continue
                if info.flag_bits & 0x1:
                    raise HTTPException(status_code=400, detail='不支援加密的 ZIP 壓縮檔。')
                if info.compress_type not in ALLOWED_ZIP_COMPRESSIONS:
                    raise HTTPException(
                        status_code=400,
                        detail='ZIP 壓縮檔使用了不支援的壓縮方式，請改用標準 Deflate 或 Store。',
                    )

                ext = posix_path.suffix.lower()
                if ext not in allowed_extensions:
                    continue

                if info.file_size > active_budget.max_single_file_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail='壓縮檔內單一檔案超過解壓上限。',
                    )
                if info.file_size > active_budget.remaining_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail='壓縮檔解壓後總容量超過上限。',
                    )

                safe_name = sanitize_filename(posix_path.name)
                out_path = _next_unique_path(dest_dir, safe_name)

                copied = 0
                try:
                    with zf.open(info, 'r') as src, out_path.open('wb') as dst:
                        while True:
                            buf = src.read(UPLOAD_CHUNK_SIZE)
                            if not buf:
                                break
                            copied += len(buf)
                            if (
                                copied > info.file_size + 1024 * 1024
                                or copied > active_budget.max_single_file_bytes
                                or copied > active_budget.remaining_bytes
                            ):
                                raise HTTPException(status_code=413, detail='壓縮檔解壓大小異常或超過上限。')
                            dst.write(buf)
                except Exception:
                    if out_path.exists():
                        out_path.unlink()
                    raise

                active_budget.remaining_bytes -= copied
                extracted.append(out_path)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError, RuntimeError, zlib.error, EOFError, OSError) as exc:
        raise HTTPException(status_code=400, detail='上傳的 ZIP 壓縮檔格式損毀、已加密或使用不支援的壓縮方式。') from exc

    if not extracted:
        raise HTTPException(status_code=400, detail='ZIP 壓縮檔內找不到支援的字型檔案。')
    return extracted


def _read_log_tail(log_path: Path, max_lines: int = 80) -> List[str]:
    if not log_path.exists():
        return []
    try:
        file_size = log_path.stat().st_size
        if file_size == 0:
            return []
        offset = max(0, file_size - MAX_LOG_READ_BYTES)
        with log_path.open('rb') as fp:
            if offset > 0:
                fp.seek(offset)
            raw = fp.read(MAX_LOG_READ_BYTES)
    except OSError:
        return []

    text = raw.decode('utf-8', errors='replace')
    lines = text.splitlines()
    if offset > 0 and len(lines) > 1:
        lines = lines[1:]
    cleaned = [line.rstrip() for line in lines if line.strip()]
    return cleaned[-max_lines:]


def _terminate_process_group(
    proc: subprocess.Popen,
    wait_timeout: float = 3.0,
    pgid: Optional[int] = None,
) -> None:
    """Terminate a worker and its entire native child process group cleanly."""
    resolved_pgid: Optional[int] = pgid
    if resolved_pgid is None and os.name == 'posix':
        try:
            resolved_pgid = os.getpgid(proc.pid)
        except ProcessLookupError:
            resolved_pgid = proc.pid

    try:
        if proc.poll() is None:
            if resolved_pgid is not None:
                os.killpg(resolved_pgid, signal.SIGTERM)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=wait_timeout)
            except subprocess.TimeoutExpired:
                if resolved_pgid is not None:
                    os.killpg(resolved_pgid, signal.SIGKILL)
                else:
                    proc.kill()
                proc.wait(timeout=wait_timeout)
    except ProcessLookupError:
        pass
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=1.0)
        except Exception:
            pass
    finally:
        # Ensure any descendant child processes still remaining in pgid are killed even if leader exited
        if resolved_pgid is not None:
            try:
                os.killpg(resolved_pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception:
                pass


def _cleanup_job_intermediates(job_dir: Path, remove_outputs: bool = False) -> None:
    """Remove per-job uploads, scratch TMPDIR, and intermediate staging dirs."""
    shutil.rmtree(job_dir / 'inputs', ignore_errors=True)
    shutil.rmtree(job_dir / 'tmp', ignore_errors=True)
    outputs_dir = job_dir / 'outputs'
    if remove_outputs:
        shutil.rmtree(outputs_dir, ignore_errors=True)
    else:
        shutil.rmtree(outputs_dir / 'family_files', ignore_errors=True)
        shutil.rmtree(outputs_dir / 'vf_files', ignore_errors=True)


class JobManager:
    """Thread-safe queue and isolated subprocess runner for font compilation jobs."""

    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings
        self.settings.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: Dict[str, dict] = {}
        self._pending_dirs: Dict[str, float] = {}
        self._admitted_pending_dirs: Set[str] = set()
        self._active_uploads: int = 0
        self._shutting_down: bool = False
        self._queue_order: List[str] = []
        self._processes: Dict[str, subprocess.Popen] = {}
        self._pgids: Dict[str, int] = {}
        self._active_downloads: Dict[str, int] = {}
        self._pending_deletes: Set[str] = set()
        self._executor = ThreadPoolExecutor(
            max_workers=self.settings.max_concurrent_jobs,
            thread_name_prefix='opencc-font-worker',
        )
        self._stop_event = threading.Event()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._load_existing_jobs()
        self._cleanup_orphaned_dirs(max_age_seconds=0.0)

    def start(self) -> None:
        """Start background TTL cleanup thread."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        self._stop_event.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name='opencc-job-cleaner',
            daemon=True,
        )
        self._cleanup_thread.start()

    def shutdown(self) -> None:
        """Stop accepting new jobs, stop cleanup, and terminate active worker process groups."""
        self._stop_event.set()
        with self._lock:
            self._shutting_down = True
            procs = [(proc, self._pgids.get(job_id)) for job_id, proc in self._processes.items()]
        for proc, pgid in procs:
            _terminate_process_group(proc, pgid=pgid)
        if sys.version_info >= (3, 9):
            self._executor.shutdown(wait=False, cancel_futures=True)
        else:
            self._executor.shutdown(wait=False)

    def _job_dir(self, job_id: str) -> Path:
        return self.settings.storage_dir / job_id

    def _meta_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / 'meta.json'

    def _save_meta(self, record: dict) -> None:
        job_dir = self._job_dir(record['job_id'])
        if not job_dir.exists():
            return
        tmp = job_dir / 'meta.json.tmp'
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self._meta_path(record['job_id']))

    def _load_existing_jobs(self) -> None:
        """Reload surviving jobs on disk; mark interrupted running/queued jobs as failed."""
        now = utc_now()
        if not self.settings.storage_dir.exists():
            return
        for entry in self.settings.storage_dir.iterdir():
            if not entry.is_dir():
                continue
            meta_file = entry / 'meta.json'
            if not meta_file.exists():
                continue
            try:
                record = json.loads(meta_file.read_text(encoding='utf-8'))
                if record.get('status') in ('queued', 'running'):
                    record['status'] = 'failed'
                    record['phase'] = 'interrupted'
                    record['error'] = '伺服器已重新啟動，先前的任務已中止。'
                    record['finished_at'] = now.isoformat()
                    record['expires_at'] = (now + timedelta(seconds=self.settings.job_ttl_seconds)).isoformat()
                    _cleanup_job_intermediates(entry, remove_outputs=True)
                    self._save_meta(record)
                expires_at = datetime.fromisoformat(record['expires_at'])
                if expires_at <= now:
                    shutil.rmtree(entry, ignore_errors=True)
                    continue
                self._jobs[record['job_id']] = record
            except Exception:
                shutil.rmtree(entry, ignore_errors=True)

    def _cleanup_orphaned_dirs(self, max_age_seconds: Optional[float] = None) -> None:
        if not self.settings.storage_dir.exists():
            return
        effective_max_age = (
            max(float(ORPHAN_INGESTION_AGE_SECONDS), float(self.settings.job_timeout_seconds))
            if max_age_seconds is None
            else float(max_age_seconds)
        )
        now_ts = time.time()
        to_remove: List[Path] = []
        with self._lock:
            for entry in self.settings.storage_dir.iterdir():
                if not entry.is_dir():
                    continue
                job_id = entry.name
                if job_id in self._jobs:
                    continue
                if (entry / 'meta.json').exists():
                    continue
                pending_since = self._pending_dirs.get(job_id)
                if pending_since is not None and (now_ts - pending_since) < effective_max_age:
                    continue
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                if effective_max_age <= 0 or (now_ts - mtime) >= effective_max_age:
                    self._pending_dirs.pop(job_id, None)
                    self._admitted_pending_dirs.discard(job_id)
                    to_remove.append(entry)
        for orphan in to_remove:
            shutil.rmtree(orphan, ignore_errors=True)

    def counts(self) -> Tuple[int, int]:
        """Return (running_jobs, queued_jobs)."""
        with self._lock:
            running = sum(1 for j in self._jobs.values() if j['status'] == 'running')
            queued = sum(1 for j in self._jobs.values() if j['status'] == 'queued')
            return running, queued

    def _reserved_queue_slots_unlocked(self, exclude_self_upload: bool = False) -> int:
        _, queued = self.counts()
        unadmitted_pending = sum(
            1 for jid in self._pending_dirs if jid not in self._admitted_pending_dirs
        )
        uploads = max(0, self._active_uploads - 1) if exclude_self_upload else self._active_uploads
        return queued + unadmitted_pending + uploads

    def acquire_upload_slot(self) -> Callable[[], None]:
        """Reserve an upload admission slot before reading multipart body."""
        with self._lock:
            if self._shutting_down:
                raise HTTPException(status_code=503, detail='伺服器正在重新啟動，暫停接收新任務。')
            if self._active_uploads >= self.settings.max_concurrent_uploads:
                raise HTTPException(status_code=503, detail='目前同時上傳請求過多，請稍後再試。')
            if self._reserved_queue_slots_unlocked() >= self.settings.max_queued_jobs:
                raise HTTPException(
                    status_code=503,
                    detail=f'目前佇列已滿（上限 {self.settings.max_queued_jobs} 筆排隊任務），請稍後再試。',
                )
            if self.settings.min_free_disk_bytes > 0:
                try:
                    free_bytes = shutil.disk_usage(self.settings.storage_dir).free
                except OSError:
                    free_bytes = self.settings.min_free_disk_bytes
                if free_bytes < self.settings.min_free_disk_bytes:
                    raise HTTPException(status_code=507, detail='伺服器暫存磁碟空間不足，請稍後再試。')
            self._active_uploads += 1

        released = False

        def _release() -> None:
            nonlocal released
            with self._lock:
                if released:
                    return
                released = True
                self._active_uploads = max(0, self._active_uploads - 1)

        return _release

    def release_upload_slot(self) -> None:
        """Release a pre-multipart upload admission slot."""
        with self._lock:
            self._active_uploads = max(0, self._active_uploads - 1)

    def create_job_dir(self, already_admitted: bool = False) -> Tuple[str, Path]:
        """Atomically reserve queue capacity and allocate an isolated directory."""
        with self._lock:
            if self._shutting_down:
                raise HTTPException(status_code=503, detail='伺服器正在重新啟動，暫停接收新任務。')
            if self._reserved_queue_slots_unlocked(exclude_self_upload=already_admitted) >= self.settings.max_queued_jobs:
                raise HTTPException(
                    status_code=503,
                    detail=f'目前佇列已滿（上限 {self.settings.max_queued_jobs} 筆排隊任務），請稍後再試。',
                )
            if self.settings.min_free_disk_bytes > 0:
                try:
                    free_bytes = shutil.disk_usage(self.settings.storage_dir).free
                except OSError:
                    free_bytes = self.settings.min_free_disk_bytes
                if free_bytes < self.settings.min_free_disk_bytes:
                    raise HTTPException(status_code=507, detail='伺服器暫存磁碟空間不足，請稍後再試。')
            job_id = uuid.uuid4().hex
            job_dir = self._job_dir(job_id)
            (job_dir / 'inputs').mkdir(parents=True, exist_ok=True)
            (job_dir / 'outputs').mkdir(parents=True, exist_ok=True)
            (job_dir / 'tmp').mkdir(parents=True, exist_ok=True)
            self._pending_dirs[job_id] = time.time()
            if already_admitted:
                self._admitted_pending_dirs.add(job_id)
            return job_id, job_dir

    def release_pending_job(self, job_id: str) -> None:
        """Release a pre-submission slot and delete any partial upload directory."""
        with self._lock:
            self._pending_dirs.pop(job_id, None)
            self._admitted_pending_dirs.discard(job_id)
        shutil.rmtree(self._job_dir(job_id), ignore_errors=True)

    def submit_job(
        self,
        job_id: str,
        mode: str,
        spec: dict,
        summary: dict,
        release_upload_slot: Optional[Callable[[], None]] = None,
    ) -> dict:
        """Persist job metadata and enqueue execution onto the worker pool."""
        now = utc_now()
        expires = now + timedelta(seconds=self.settings.job_ttl_seconds)
        job_dir = self._job_dir(job_id)

        spec_payload = {
            **spec,
            'job_id': job_id,
            'mode': mode,
            'job_dir': str(job_dir),
        }
        spec_path = job_dir / 'spec.json'
        spec_path.write_text(json.dumps(spec_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        (job_dir / 'phase.txt').write_text('queued', encoding='utf-8')

        record = {
            'job_id': job_id,
            'mode': mode,
            'status': 'queued',
            'phase': 'queued',
            'created_at': now.isoformat(),
            'started_at': None,
            'finished_at': None,
            'expires_at': expires.isoformat(),
            'summary': summary,
            'artifacts': [],
            'error': None,
        }

        with self._lock:
            if self._shutting_down:
                raise HTTPException(status_code=503, detail='伺服器正在重新啟動，暫停接收新任務。')
            self._pending_dirs.pop(job_id, None)
            self._admitted_pending_dirs.discard(job_id)
            self._jobs[job_id] = record
            self._queue_order.append(job_id)
            try:
                self._save_meta(record)
                response = self._serialize_job_unlocked(record)
                self._executor.submit(self._run_worker, job_id, spec_path)
                if release_upload_slot is not None:
                    release_upload_slot()
                return response
            except Exception:
                self._jobs.pop(job_id, None)
                if job_id in self._queue_order:
                    self._queue_order.remove(job_id)
                raise

    def _run_worker(self, job_id: str, spec_path: Path) -> None:
        job_dir = self._job_dir(job_id)
        log_path = job_dir / 'job.log'
        phase_path = job_dir / 'phase.txt'
        result_path = job_dir / 'result.json'
        job_tmp_dir = job_dir / 'tmp'
        job_tmp_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            record = self._jobs.get(job_id)
            if not record or record['status'] == 'cancelled' or self._shutting_down:
                if record and self._shutting_down and record['status'] != 'cancelled':
                    now_iso = utc_now().isoformat()
                    record['status'] = 'failed'
                    record['phase'] = 'interrupted'
                    record['error'] = '伺服器正在重新啟動，任務已取消。'
                    record['finished_at'] = now_iso
                    try:
                        self._save_meta(record)
                    except OSError:
                        pass
                if job_id in self._queue_order:
                    self._queue_order.remove(job_id)
                _cleanup_job_intermediates(job_dir, remove_outputs=True)
                return
            record['status'] = 'running'
            record['phase'] = 'initializing'
            record['started_at'] = utc_now().isoformat()
            if job_id in self._queue_order:
                self._queue_order.remove(job_id)
            try:
                self._save_meta(record)
            except OSError:
                pass

        src_dir = str(Path(__file__).resolve().parents[2])
        env = {
            'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'),
            'PYTHONPATH': src_dir,
            'PYTHONUNBUFFERED': '1',
            'PYTHONDONTWRITEBYTECODE': '1',
            'TMPDIR': str(job_tmp_dir),
            'TEMP': str(job_tmp_dir),
            'TMP': str(job_tmp_dir),
            'HOME': str(job_dir),
            'LANG': os.environ.get('LANG', 'C.UTF-8'),
            'LC_ALL': os.environ.get('LC_ALL', 'C.UTF-8'),
        }

        timed_out = False
        exit_code = -1
        launch_error: Optional[str] = None
        final_status = 'failed'

        try:
            try:
                with log_path.open('w', encoding='utf-8') as log_file:
                    popen_kwargs: dict = {
                        'cwd': str(job_dir),
                        'stdout': log_file,
                        'stderr': subprocess.STDOUT,
                        'env': env,
                    }
                    if os.name == 'posix':
                        popen_kwargs['start_new_session'] = True

                    proc = subprocess.Popen(
                        [sys.executable, '-u', '-m', 'OpenCCFontGenerator.web.worker', str(spec_path)],
                        **popen_kwargs,
                    )
                    pgid = proc.pid if os.name == 'posix' else None
                    cancelled_before_track = False
                    with self._lock:
                        current = self._jobs.get(job_id)
                        if not current or current['status'] == 'cancelled' or self._shutting_down:
                            cancelled_before_track = True
                        else:
                            self._processes[job_id] = proc
                            if pgid is not None:
                                self._pgids[job_id] = pgid

                    if cancelled_before_track:
                        _terminate_process_group(proc, pgid=pgid)
                        return

                    try:
                        exit_code = proc.wait(timeout=self.settings.job_timeout_seconds)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        _terminate_process_group(proc, pgid=pgid)
            except Exception as exc:
                launch_error = str(exc)
                try:
                    with log_path.open('a', encoding='utf-8') as log_file:
                        log_file.write(f'\nWorker launch failed: {exc}\n')
                except OSError:
                    pass
            finally:
                with self._lock:
                    self._processes.pop(job_id, None)
                    self._pgids.pop(job_id, None)

            finished_now = utc_now()
            finished_at = finished_now.isoformat()
            with self._lock:
                record = self._jobs.get(job_id)
                if not record:
                    return
                if record['status'] == 'cancelled':
                    record['finished_at'] = finished_at
                    try:
                        self._save_meta(record)
                    except OSError:
                        pass
                    return

                if timed_out:
                    record['status'] = 'failed'
                    record['phase'] = 'timed_out'
                    record['error'] = f'字型編譯超過單次上限（{self.settings.job_timeout_seconds} 秒），已自動終止。'
                elif exit_code == 0 and result_path.is_file():
                    try:
                        result_data = json.loads(result_path.read_text(encoding='utf-8'))
                        artifacts = result_data.get('artifacts') if isinstance(result_data, dict) else None
                        if not isinstance(artifacts, list) or not artifacts:
                            raise ValueError('Worker result missing valid artifacts')
                        record['status'] = 'completed'
                        record['phase'] = 'completed'
                        record['artifacts'] = artifacts
                        final_status = 'completed'
                    except Exception as exc:
                        record['status'] = 'failed'
                        record['phase'] = 'failed'
                        record['error'] = f'字型編譯產物記錄無效：{exc}'
                else:
                    record['status'] = 'failed'
                    try:
                        record['phase'] = (
                            phase_path.read_text(encoding='utf-8').strip()[:256]
                            if phase_path.exists()
                            else 'failed'
                        )
                    except OSError:
                        record['phase'] = 'failed'
                    tail = _read_log_tail(log_path, max_lines=6)
                    record['error'] = tail[-1] if tail else (
                        f'Worker 執行異常：{launch_error}' if launch_error else f'字型編譯失敗（exit code {exit_code}）。'
                    )

                record['finished_at'] = finished_at
                record['expires_at'] = (finished_now + timedelta(seconds=self.settings.job_ttl_seconds)).isoformat()
                try:
                    self._save_meta(record)
                except OSError:
                    pass
        except Exception as exc:
            with self._lock:
                record = self._jobs.get(job_id)
                if record and record['status'] in ('queued', 'running'):
                    now_dt = utc_now()
                    record['status'] = 'failed'
                    record['phase'] = 'failed'
                    record['error'] = f'任務執行期間發生未預期錯誤：{exc}'
                    record['finished_at'] = now_dt.isoformat()
                    record['expires_at'] = (now_dt + timedelta(seconds=self.settings.job_ttl_seconds)).isoformat()
                    try:
                        self._save_meta(record)
                    except OSError:
                        pass
        finally:
            _cleanup_job_intermediates(job_dir, remove_outputs=(final_status != 'completed'))

    def _serialize_job_unlocked(self, record: dict, log_tail: Optional[List[str]] = None) -> dict:
        job_id = record['job_id']
        job_dir = self._job_dir(job_id)
        phase = record['phase']
        if record['status'] == 'running':
            phase_file = job_dir / 'phase.txt'
            if phase_file.exists():
                phase = phase_file.read_text(encoding='utf-8').strip()[:256] or phase

        queue_pos = 0
        if record['status'] == 'queued' and job_id in self._queue_order:
            queue_pos = self._queue_order.index(job_id) + 1

        elapsed = None
        if record.get('started_at'):
            start_dt = datetime.fromisoformat(record['started_at'])
            end_dt = datetime.fromisoformat(record['finished_at']) if record.get('finished_at') else utc_now()
            elapsed = round(max(0.0, (end_dt - start_dt).total_seconds()), 2)

        artifacts = [
            {
                **art,
                'download_url': f"/api/v1/jobs/{job_id}/artifacts/{quote(art['filename'], safe='')}",
            }
            for art in record.get('artifacts', [])
        ]

        primary_url = None
        if record['status'] == 'completed' and artifacts:
            primary_url = f'/api/v1/jobs/{job_id}/download'

        return {
            'job_id': job_id,
            'mode': record['mode'],
            'status': record['status'],
            'phase': phase,
            'queue_position': queue_pos,
            'created_at': record['created_at'],
            'started_at': record.get('started_at'),
            'finished_at': record.get('finished_at'),
            'expires_at': record['expires_at'],
            'elapsed_seconds': elapsed,
            'summary': record.get('summary', {}),
            'artifacts': artifacts,
            'download_url': primary_url,
            'log_tail': _read_log_tail(job_dir / 'job.log') if log_tail is None else log_tail,
            'error': record.get('error'),
        }

    def get_job(self, job_id: str) -> Optional[dict]:
        """Return serialized job status by ID, or None if missing/expired."""
        if not JOB_ID_RE.fullmatch(job_id):
            return None
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return None
            record_snapshot = dict(record)
        log_tail = _read_log_tail(self._job_dir(job_id) / 'job.log')
        with self._lock:
            record = self._jobs.get(job_id) or record_snapshot
            return self._serialize_job_unlocked(record, log_tail=log_tail)

    def _resolve_artifact_path_unlocked(self, job_id: str, filename: Optional[str] = None) -> Tuple[Path, str]:
        if job_id in self._pending_deletes:
            raise HTTPException(status_code=404, detail='找不到指定的任務 ID 或任務已過期清除。')
        record = self._jobs.get(job_id)
        if not record:
            raise HTTPException(status_code=404, detail='找不到指定的任務 ID 或任務已過期清除。')
        if record['status'] != 'completed':
            raise HTTPException(status_code=409, detail=f"任務目前狀態為「{record['status']}」，尚未完成下載準備。")
        artifacts = record.get('artifacts', [])
        if not artifacts:
            raise HTTPException(status_code=404, detail='此任務沒有可下載的輸出檔案。')

        if filename is None:
            selected = next((a for a in artifacts if a.get('primary')), artifacts[0])
        else:
            selected = next((a for a in artifacts if a['filename'] == filename), None)

        if not selected:
            raise HTTPException(status_code=404, detail='找不到指定的輸出檔案。')

        outputs_dir = (self._job_dir(job_id) / 'outputs').resolve()
        file_path = (outputs_dir / selected['filename']).resolve()
        if not is_within_dir(file_path, outputs_dir) or not file_path.is_file():
            raise HTTPException(status_code=404, detail='輸出檔案不存在或已被清除。')

        return file_path, selected['filename']

    def get_artifact_path(self, job_id: str, filename: Optional[str] = None) -> Tuple[Path, str]:
        """Resolve an artifact file path safely under the job's outputs directory."""
        if not JOB_ID_RE.fullmatch(job_id):
            raise HTTPException(status_code=404, detail='找不到指定的任務 ID。')
        with self._lock:
            return self._resolve_artifact_path_unlocked(job_id, filename=filename)

    def get_artifact_for_download(
        self,
        job_id: str,
        filename: Optional[str] = None,
    ) -> Tuple[Path, str, Callable[[], None]]:
        """Acquire a download lease preventing deletion until streaming finishes."""
        if not JOB_ID_RE.fullmatch(job_id):
            raise HTTPException(status_code=404, detail='找不到指定的任務 ID。')
        with self._lock:
            file_path, resolved_name = self._resolve_artifact_path_unlocked(job_id, filename=filename)
            self._active_downloads[job_id] = self._active_downloads.get(job_id, 0) + 1

        released = False

        def _release() -> None:
            nonlocal released
            should_remove = False
            with self._lock:
                if released:
                    return
                released = True
                remaining = self._active_downloads.get(job_id, 0) - 1
                if remaining > 0:
                    self._active_downloads[job_id] = remaining
                else:
                    self._active_downloads.pop(job_id, None)
                    if job_id in self._pending_deletes:
                        self._pending_deletes.discard(job_id)
                        should_remove = True
            if should_remove:
                shutil.rmtree(self._job_dir(job_id), ignore_errors=True)

        return file_path, resolved_name, _release

    def delete_job(self, job_id: str) -> bool:
        """Cancel running/queued job if needed and remove its disk directory (deferred if downloading)."""
        if not JOB_ID_RE.fullmatch(job_id):
            return False
        proc: Optional[subprocess.Popen] = None
        pgid: Optional[int] = None
        defer_rm = False
        with self._lock:
            record = self._jobs.pop(job_id, None)
            if not record:
                return False
            record['status'] = 'cancelled'
            if job_id in self._queue_order:
                self._queue_order.remove(job_id)
            proc = self._processes.pop(job_id, None)
            pgid = self._pgids.pop(job_id, None)
            if self._active_downloads.get(job_id, 0) > 0:
                self._pending_deletes.add(job_id)
                defer_rm = True
        if proc is not None:
            _terminate_process_group(proc, pgid=pgid)
        if not defer_rm:
            shutil.rmtree(self._job_dir(job_id), ignore_errors=True)
        return True

    def purge_expired(self) -> int:
        """Delete expired jobs and abandoned ingestion directories whose TTL has elapsed."""
        now = utc_now()
        expired_ids = []
        delete_now_ids = []
        with self._lock:
            for job_id, record in list(self._jobs.items()):
                if record['status'] in ('running', 'queued'):
                    continue
                expires_at = datetime.fromisoformat(record['expires_at'])
                if expires_at <= now:
                    expired_ids.append(job_id)
                    self._jobs.pop(job_id, None)
                    if self._active_downloads.get(job_id, 0) > 0:
                        self._pending_deletes.add(job_id)
                    else:
                        delete_now_ids.append(job_id)
        for job_id in delete_now_ids:
            shutil.rmtree(self._job_dir(job_id), ignore_errors=True)
        self._cleanup_orphaned_dirs()
        return len(expired_ids)

    def _cleanup_loop(self) -> None:
        while not self._stop_event.wait(self.settings.cleanup_interval_seconds):
            try:
                self.purge_expired()
            except Exception:
                pass
