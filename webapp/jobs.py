"""
Executa downloads do YouTube (downloader.py) em thread de background, um diretório por job.

Mesma lógica da versão hospedada (dev-ops/apps/tube-fetch/jobs.py): arquivo `job.json` + token
aleatório por job para permitir polling seguro. Aqui, versão local/desktop: sem conceito de
usuário/login (single-user, sua própria máquina), e o diretório de trabalho fica em
%LOCALAPPDATA% no Windows (ou equivalente/temp em outros sistemas) em vez de /tmp de um Pod.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import tempfile
import threading
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from downloader import VALID_MODES, DownloadError, run_job


def _default_jobs_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or tempfile.gettempdir()
    return Path(base) / "TubeFetchDesktop" / "jobs"


JOBS_ROOT = Path(os.environ.get("TUBEFETCH_DESKTOP_JOBS_DIR") or _default_jobs_dir())
JOB_TTL_SECONDS = int(os.environ.get("TUBEFETCH_DESKTOP_JOB_TTL_SECONDS", str(6 * 3600)))
MAX_COOKIES_BYTES = int(os.environ.get("TUBEFETCH_DESKTOP_MAX_COOKIES_BYTES", str(256 * 1024)))
LOG_TAIL_BYTES = int(os.environ.get("TUBEFETCH_DESKTOP_LOG_TAIL_BYTES", str(32768)))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    id: str
    token: str
    status: str  # queued | running | completed | failed
    mode: str
    url: str
    created: str
    started: str | None
    finished: str | None
    error: str | None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def ensure_jobs_root() -> None:
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)


def _job_dir(job_id: str) -> Path:
    return JOBS_ROOT / job_id


def _downloads_dir(job_id: str) -> Path:
    return _job_dir(job_id) / "downloads"


def _record_path(job_id: str) -> Path:
    return _job_dir(job_id) / "job.json"


def _write_record(job_id: str, rec: JobRecord) -> None:
    _record_path(job_id).write_text(json.dumps(rec.to_json(), indent=2), encoding="utf-8")


def _read_record(job_id: str) -> JobRecord | None:
    p = _record_path(job_id)
    if not p.exists():
        return None
    return JobRecord(**json.loads(p.read_text(encoding="utf-8")))


def read_log_tail(job_id: str) -> str:
    p = _job_dir(job_id) / "job.log"
    if not p.exists():
        return ""
    data = p.read_bytes()
    if len(data) > LOG_TAIL_BYTES:
        data = b"...[truncado]\n" + data[-LOG_TAIL_BYTES:]
    return data.decode("utf-8", errors="replace")


def list_job_files(job_id: str) -> list[dict[str, Any]]:
    d = _downloads_dir(job_id)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.iterdir()):
        if p.is_file() and p.suffix not in (".part", ".ytdl"):
            out.append({"name": p.name, "size": p.stat().st_size})
    return out


def resolve_job_file(job_id: str, filename: str) -> Path | None:
    """Resolve o caminho com proteção contra path traversal; None se inválido ou inexistente."""
    d = _downloads_dir(job_id).resolve()
    candidate = (d / filename).resolve()
    if candidate.parent != d:
        return None
    if not candidate.is_file():
        return None
    return candidate


def build_zip(job_id: str) -> Path | None:
    files = list_job_files(job_id)
    if not files:
        return None
    zip_path = _job_dir(job_id) / "download.zip"
    if zip_path.exists():
        return zip_path
    d = _downloads_dir(job_id)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(d / f["name"], arcname=f["name"])
    return zip_path


def _execute(job_id: str, params: dict[str, Any]) -> None:
    rec = _read_record(job_id)
    if rec is None:
        return
    rec.status = "running"
    rec.started = _utc_now()
    _write_record(job_id, rec)

    downloads_dir = _downloads_dir(job_id)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    log_path = _job_dir(job_id) / "job.log"

    cookiefile = params.pop("cookiefile", None)
    status, error = "completed", None
    try:
        run_job(output_dir=downloads_dir, log_path=log_path, cookiefile=cookiefile, **params)
    except DownloadError as e:
        status, error = "failed", str(e)
    except Exception as e:  # noqa: BLE001 — nunca deixar a thread morrer sem atualizar o job.json
        status, error = "failed", f"Erro inesperado: {e}"

    rec = _read_record(job_id)
    if rec is None:
        return
    rec.status = status
    rec.error = error
    rec.finished = _utc_now()
    _write_record(job_id, rec)


def cleanup_old_jobs() -> None:
    ensure_jobs_root()
    now = time.time()
    for p in JOBS_ROOT.iterdir():
        if not p.is_dir():
            continue
        try:
            age = now - p.stat().st_mtime
        except OSError:
            continue
        if age > JOB_TTL_SECONDS:
            shutil.rmtree(p, ignore_errors=True)


def start_job(
    *,
    url: str,
    mode: str,
    sub_lang: str,
    sub_auto: bool,
    cookies_bytes: bytes | None,
) -> tuple[JobRecord | None, str | None]:
    """Cria o diretório do job e dispara a thread de download. Retorna (JobRecord, None) ou (None, erro)."""
    ensure_jobs_root()
    cleanup_old_jobs()

    if not url.strip():
        return None, "Informe a URL do vídeo ou playlist."
    if mode not in VALID_MODES:
        return None, "Modo de download inválido."

    job_id = secrets.token_hex(16)
    token = secrets.token_urlsafe(32)
    job_dir = _job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    cookiefile: Path | None = None
    if cookies_bytes:
        cookiefile = job_dir / "cookies.txt"
        cookiefile.write_bytes(cookies_bytes)

    rec = JobRecord(
        id=job_id,
        token=token,
        status="queued",
        mode=mode,
        url=url,
        created=_utc_now(),
        started=None,
        finished=None,
        error=None,
    )
    _write_record(job_id, rec)

    params = {
        "mode": mode,
        "url": url,
        "sub_lang": sub_lang or "pt",
        "sub_auto": sub_auto,
        "cookiefile": cookiefile,
    }
    t = threading.Thread(target=_execute, args=(job_id, params), daemon=True)
    t.start()
    return rec, None


def get_job(job_id: str, token: str) -> tuple[JobRecord | None, str | None]:
    rec = _read_record(job_id)
    if rec is None:
        return None, "Job não encontrado."
    if not secrets.compare_digest(rec.token, token):
        return None, "Token inválido."
    return rec, None
