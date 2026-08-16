"""
Tube Fetch Desktop — versão local (Windows) da interface web de download do YouTube (yt-dlp).

Mesmo motor da versão hospedada na nuvem (dev-ops/apps/tube-fetch), sem login, banco de dados
nem multiusuário — feito para rodar na sua própria máquina. Como usa o seu IP residencial (não
o de um datacenter), a grande maioria dos vídeos baixa sem precisar de cookies.txt.
"""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from downloader import VALID_MODES
from jobs import (
    MAX_COOKIES_BYTES,
    build_zip,
    get_job,
    list_job_files,
    read_log_tail,
    resolve_job_file,
    start_job,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_COOKIES_BYTES + (64 * 1024)

MODE_LABELS = {
    "video": "Vídeo (.mp4)",
    "audio": "Áudio (.mp3)",
    "playlist_video": "Playlist — vídeos (.mp4)",
    "playlist_audio": "Playlist — áudio (.mp3)",
    "subtitles": "Legendas (.srt)",
}

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_static_versions: dict[str, str] = {}


def _static_version(filename: str) -> str:
    cached = _static_versions.get(filename)
    if cached is not None:
        return cached
    try:
        digest = hashlib.sha1((_STATIC_DIR / filename).read_bytes()).hexdigest()[:10]
    except OSError:
        digest = "0"
    _static_versions[filename] = digest
    return digest


@app.context_processor
def _inject_static_version():
    return {"static_version": _static_version}


@app.errorhandler(413)
def request_entity_too_large(_e):
    return jsonify({"error": "Arquivo de cookies muito grande."}), 413


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "tube-fetch-desktop"})


@app.route("/")
def index():
    return render_template("dashboard.html", modes=MODE_LABELS)


@app.route("/api/jobs", methods=["POST"])
def api_jobs_create():
    url = (request.form.get("url") or "").strip()
    mode = (request.form.get("mode") or "").strip()
    sub_lang = (request.form.get("sub_lang") or "pt").strip()
    sub_auto = request.form.get("sub_auto") in ("on", "true", "1", "yes")

    if mode not in VALID_MODES:
        return jsonify({"error": "Escolha um modo de download válido."}), 400
    if not url:
        return jsonify({"error": "Informe a URL do vídeo ou playlist."}), 400

    cookies_bytes = None
    cookies_file = request.files.get("cookies")
    if cookies_file and getattr(cookies_file, "filename", None):
        cookies_bytes = cookies_file.read()

    rec, err = start_job(url=url, mode=mode, sub_lang=sub_lang, sub_auto=sub_auto, cookies_bytes=cookies_bytes)
    if err:
        return jsonify({"error": err}), 400
    assert rec is not None
    return jsonify({"id": rec.id, "token": rec.token, "status": rec.status})


@app.route("/api/jobs/<job_id>", methods=["GET"])
def api_jobs_status(job_id: str):
    token = (request.args.get("token") or "").strip()
    if not token:
        return jsonify({"error": "Informe token= na query."}), 400
    rec, err = get_job(job_id, token)
    if err:
        return jsonify({"error": err}), 404
    assert rec is not None
    return jsonify(
        {
            "id": rec.id,
            "status": rec.status,
            "mode": rec.mode,
            "url": rec.url,
            "created": rec.created,
            "started": rec.started,
            "finished": rec.finished,
            "error": rec.error,
            "skipped": rec.skipped,
            "log": read_log_tail(job_id),
            "files": list_job_files(job_id),
        }
    )


@app.route("/jobs/<job_id>/files/<path:filename>")
def download_job_file(job_id: str, filename: str):
    token = (request.args.get("token") or "").strip()
    _rec, err = get_job(job_id, token)
    if err:
        abort(404)
    path = resolve_job_file(job_id, filename)
    if path is None:
        abort(404)
    mime, _enc = mimetypes.guess_type(path.name)
    return send_file(
        path, mimetype=mime or "application/octet-stream", as_attachment=True, download_name=path.name
    )


@app.route("/jobs/<job_id>/zip")
def download_job_zip(job_id: str):
    token = (request.args.get("token") or "").strip()
    _rec, err = get_job(job_id, token)
    if err:
        abort(404)
    zip_path = build_zip(job_id)
    if zip_path is None:
        abort(404)
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"tube-fetch-{job_id[:8]}.zip",
    )
