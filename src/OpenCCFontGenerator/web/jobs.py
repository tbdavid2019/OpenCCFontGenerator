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
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Set, Tuple
import uuid
import zipfile

from fastapi import HTTPException, UploadFile

from .config import WebSettings


FONT_EXTENSIONS = {'.ttf', '.otf', '.ttc', '.woff2'}
ROTATE_EXTENSIONS = {'.ttf', '.otf', '.ttc'}
WEBFONT_EXTENSIONS = {'.ttf', '.otf'}
ARCHIVE_EXTENSIONS = {'.zip'}
JSON_EXTENSIONS = {'.json'}

MAX_ARCHIVE_ENTRIES = 64
MAX_UNIQUE_NAME_ATTEMPTS = 100
MAX_LOG_READ_BYTES = 32 * 1024
ORPHAN_INGESTION_AGE_SECONDS = 900
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MiB


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


def sanitize_filename(filename: Optional[str], fallback: str = 'font.ttf') -> str:
    """Strip directory paths and unsafe characters while keeping extension intact."""
    base = Path(filename or fallback).name
    raw_stem = Path(base).stem
    raw_suffix = Path(base).suffix
    clean_suffix = re.sub(r'[^A-Za-z0-9.]+', '', raw_suffix)[:16]
    clean_stem = re.sub(r'[^A-Za-z0-9._()\-\u4e00-\u9fff]+', '_', raw_stem).strip('._')
    if not clean_stem:
        clean_stem = Path(fallback).stem or 'file'
    max_stem_len = max(1, 160 - len(clean_suffix))
    result = f'{clean_stem[:max_stem_len]}{clean_suffix}'
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
    extracted: List[Path] = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            infos = [info for info in zf.infolist() if not info.is_dir()]
            if len(infos) > active_budget.remaining_entries:
                raise HTTPException(
                    status_code=400,
                    detail=f'壓縮檔內檔案數量過多（單次請求最多 {MAX_ARCHIVE_ENTRIES} 個）。',
                )
            active_budget.remaining_entries -= len(infos)

            for info in infos:
                raw_name = info.filename.replace('\\', '/')
                posix_path = PurePosixPath(raw_name)
                if raw_name.startswith('/') or '..' in posix_path.parts or ':' in posix_path.parts[0]:
                    raise HTTPException(status_code=400, detail='壓縮檔包含不安全的路徑。')

                # Skip macOS metadata and hidden entries
                if '__MACOSX' in posix_path.parts or posix_path.name.startswith('.'):
                    continue
                # Reject POSIX symlinks
                if info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000:
                    continue

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
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail='上傳的 ZIP 壓縮檔格式損毀或無效。') from exc

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


def _terminate_process_group(proc: subprocess.Popen, wait_timeout: float = 3.0) -> None:
    """Terminate a worker and its entire native child process group cleanly."""
    pgid: Optional[int] = None
    if os.name == 'posix':
        try:
            pgid = os.getpgid(proc.pid)
        except ProcessLookupError:
            pgid = None

    try:
        if proc.poll() is None:
            if pgid is not None:
                os.killpg(pgid, signal.SIGTERM)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=wait_timeout)
            except subprocess.TimeoutExpired:
                if pgid is not None:
                    os.killpg(pgid, signal.SIGKILL)
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
        # Ensure any descendant child processes still remaining in pgid are killed
        if pgid is not None:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception:
                pass


class JobManager:
    """Thread-safe queue and isolated subprocess runner for font compilation jobs."""

    def __init__(self, settings: WebSettings) -> None:
        self.settings = settings
        self.settings.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: Dict[str, dict] = {}
        self._pending_dirs: Dict[str, float] = {}
        self._queue_order: List[str] = []
        self._processes: Dict[str, subprocess.Popen] = {}
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
        """Stop background cleanup and terminate active worker process groups."""
        self._stop_event.set()
        with self._lock:
            procs = list(self._processes.values())
        for proc in procs:
            _terminate_process_group(proc)
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
                    self._save_meta(record)
                expires_at = datetime.fromisoformat(record['expires_at'])
                if expires_at <= now:
                    shutil.rmtree(entry, ignore_errors=True)
                    continue
                self._jobs[record['job_id']] = record
            except Exception:
                shutil.rmtree(entry, ignore_errors=True)

    def _cleanup_orphaned_dirs(self, max_age_seconds: float = ORPHAN_INGESTION_AGE_SECONDS) -> None:
        if not self.settings.storage_dir.exists():
            return
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
                if pending_since is not None and (now_ts - pending_since) < max_age_seconds:
                    continue
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                if max_age_seconds <= 0 or (now_ts - mtime) >= max_age_seconds:
                    self._pending_dirs.pop(job_id, None)
                    to_remove.append(entry)
        for orphan in to_remove:
            shutil.rmtree(orphan, ignore_errors=True)

    def counts(self) -> Tuple[int, int]:
        """Return (running_jobs, queued_jobs)."""
        with self._lock:
            running = sum(1 for j in self._jobs.values() if j['status'] == 'running')
            queued = sum(1 for j in self._jobs.values() if j['status'] == 'queued')
            return running, queued

    def create_job_dir(self) -> Tuple[str, Path]:
        """Atomically reserve queue capacity and allocate an isolated directory."""
        with self._lock:
            _, queued = self.counts()
            if (queued + len(self._pending_dirs)) >= self.settings.max_queued_jobs:
                raise HTTPException(
                    status_code=503,
                    detail=f'目前佇列已滿（上限 {self.settings.max_queued_jobs} 筆排隊任務），請稍後再試。',
                )
            job_id = uuid.uuid4().hex[:12]
            job_dir = self._job_dir(job_id)
            (job_dir / 'inputs').mkdir(parents=True, exist_ok=True)
            (job_dir / 'outputs').mkdir(parents=True, exist_ok=True)
            self._pending_dirs[job_id] = time.time()
            return job_id, job_dir

    def release_pending_job(self, job_id: str) -> None:
        """Release a pre-submission slot and delete any partial upload directory."""
        with self._lock:
            self._pending_dirs.pop(job_id, None)
        shutil.rmtree(self._job_dir(job_id), ignore_errors=True)

    def submit_job(self, job_id: str, mode: str, spec: dict, summary: dict) -> dict:
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
            self._pending_dirs.pop(job_id, None)
            self._jobs[job_id] = record
            self._queue_order.append(job_id)
            self._save_meta(record)
            response = self._serialize_job_unlocked(record)

        self._executor.submit(self._run_worker, job_id, spec_path)
        return response

    def _run_worker(self, job_id: str, spec_path: Path) -> None:
        job_dir = self._job_dir(job_id)
        log_path = job_dir / 'job.log'
        phase_path = job_dir / 'phase.txt'
        result_path = job_dir / 'result.json'

        with self._lock:
            record = self._jobs.get(job_id)
            if not record or record['status'] == 'cancelled':
                return
            record['status'] = 'running'
            record['phase'] = 'initializing'
            record['started_at'] = utc_now().isoformat()
            if job_id in self._queue_order:
                self._queue_order.remove(job_id)
            self._save_meta(record)

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        src_dir = str(Path(__file__).resolve().parents[2])
        env['PYTHONPATH'] = src_dir

        timed_out = False
        exit_code = -1

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
                cancelled_before_track = False
                with self._lock:
                    current = self._jobs.get(job_id)
                    if not current or current['status'] == 'cancelled':
                        cancelled_before_track = True
                    else:
                        self._processes[job_id] = proc

                if cancelled_before_track:
                    _terminate_process_group(proc)
                    return

                try:
                    exit_code = proc.wait(timeout=self.settings.job_timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    _terminate_process_group(proc)
        except Exception as exc:
            with log_path.open('a', encoding='utf-8') as log_file:
                log_file.write(f'\nWorker launch failed: {exc}\n')
        finally:
            with self._lock:
                self._processes.pop(job_id, None)

        finished_now = utc_now()
        finished_at = finished_now.isoformat()
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return
            if record['status'] == 'cancelled':
                record['finished_at'] = finished_at
                self._save_meta(record)
                return

            if timed_out:
                record['status'] = 'failed'
                record['phase'] = 'timed_out'
                record['error'] = f'字型編譯超過單次上限（{self.settings.job_timeout_seconds} 秒），已自動終止。'
            elif exit_code == 0 and result_path.exists():
                result_data = json.loads(result_path.read_text(encoding='utf-8'))
                record['status'] = 'completed'
                record['phase'] = 'completed'
                record['artifacts'] = result_data.get('artifacts', [])
            else:
                record['status'] = 'failed'
                record['phase'] = (
                    phase_path.read_text(encoding='utf-8').strip()[:256]
                    if phase_path.exists()
                    else 'failed'
                )
                tail = _read_log_tail(log_path, max_lines=6)
                record['error'] = tail[-1] if tail else f'字型編譯失敗（exit code {exit_code}）。'

            record['finished_at'] = finished_at
            record['expires_at'] = (finished_now + timedelta(seconds=self.settings.job_ttl_seconds)).isoformat()
            self._save_meta(record)

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
                'download_url': f"/api/v1/jobs/{job_id}/artifacts/{art['filename']}",
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
        if not re.fullmatch(r'[a-f0-9]{12}', job_id):
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

    def get_artifact_path(self, job_id: str, filename: Optional[str] = None) -> Tuple[Path, str]:
        """Resolve an artifact file path safely under the job's outputs directory."""
        if not re.fullmatch(r'[a-f0-9]{12}', job_id):
            raise HTTPException(status_code=404, detail='找不到指定的任務 ID。')
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                raise HTTPException(status_code=404, detail='找不到指定的任務 ID 或任務已過期清除。')
            if record['status'] != 'completed':
                raise HTTPException(status_code=409, detail=f"任務目前狀態為「{record['status']}」，尚未完成下載準備。")
            artifacts = record.get('artifacts', [])
            if not artifacts:
                raise HTTPException(status_code=404, detail='此任務沒有可下載的輸出檔案。')

            selected = None
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

    def delete_job(self, job_id: str) -> bool:
        """Cancel running/queued job if needed and remove its disk directory."""
        if not re.fullmatch(r'[a-f0-9]{12}', job_id):
            return False
        proc: Optional[subprocess.Popen] = None
        with self._lock:
            record = self._jobs.pop(job_id, None)
            if not record:
                return False
            record['status'] = 'cancelled'
            if job_id in self._queue_order:
                self._queue_order.remove(job_id)
            proc = self._processes.pop(job_id, None)
        if proc is not None:
            _terminate_process_group(proc)
        shutil.rmtree(self._job_dir(job_id), ignore_errors=True)
        return True

    def purge_expired(self) -> int:
        """Delete expired jobs and abandoned ingestion directories whose TTL has elapsed."""
        now = utc_now()
        expired_ids = []
        with self._lock:
            for job_id, record in list(self._jobs.items()):
                if record['status'] in ('running', 'queued'):
                    continue
                expires_at = datetime.fromisoformat(record['expires_at'])
                if expires_at <= now:
                    expired_ids.append(job_id)
                    self._jobs.pop(job_id, None)
        for job_id in expired_ids:
            shutil.rmtree(self._job_dir(job_id), ignore_errors=True)
        self._cleanup_orphaned_dirs()
        return len(expired_ids)

    def _cleanup_loop(self) -> None:
        while not self._stop_event.wait(self.settings.cleanup_interval_seconds):
            try:
                self.purge_expired()
            except Exception:
                pass
