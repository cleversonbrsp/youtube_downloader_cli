"""
Núcleo de download com yt-dlp: vídeo, áudio, playlist (vídeo/áudio) e legendas.

Adaptado do CLI original (youtube_downloader_cli/main.py) para rodar dentro de um job de
background (ver jobs.py): nada de prompts interativos — todos os parâmetros chegam explícitos
do formulário web, e as mensagens do yt-dlp vão para um arquivo de log por job (lido pela UI).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yt_dlp

# Evita 403 no YouTube: prioriza clientes com URLs diretas (android/tv) em vez de SABR (web).
# Mesmo truque usado no CLI original, mas "tv_embedded" foi descontinuado pelo YouTube/yt-dlp
# (o yt-dlp passa a ignorá-lo e cai num cliente que pede confirmação anti-bot). Lista atual de
# clientes válidos: conferir yt_dlp.extractor.youtube._base.INNERTUBE_CLIENTS na versão instalada.
#
# "web" volta à lista porque agora há um PO Token provider (bgutil-ytdlp-pot-provider, sidecar no
# mesmo Pod, ver platform/charts/tube-fetch/values.yaml → potProvider) — é o client mais completo
# (formatos/legendas) e o alvo principal desse provider; os demais continuam como fallback já que
# em geral não exigem token vindo de IP de datacenter.
EXTRACTOR_ARGS_YOUTUBE = {
    "youtube": {
        "player_client": ["android", "ios", "tv", "tv_simply", "web"],
    },
    # Sidecar no mesmo Pod (rede compartilhada) — ver Deployment do chart tube-fetch.
    "youtubepot-bgutilhttp": {
        "base_url": ["http://127.0.0.1:4416"],
    },
}

VALID_MODES = {"video", "audio", "playlist_video", "playlist_audio", "subtitles"}


class DownloadError(RuntimeError):
    """Erro esperado (URL inválida, formato indisponível, bloqueio anti-bot) — mensagem amigável."""


class _JobLogger:
    """Recebe as mensagens do yt-dlp (objeto `logger`) e grava num arquivo de log por job."""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    def _write(self, level: str, msg: str) -> None:
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"[{level}] {msg}\n")
        except OSError:
            pass

    def debug(self, msg: str) -> None:
        # yt-dlp manda muita coisa em debug; ficamos só com as linhas úteis de progresso/etapas.
        if msg.startswith(("[download]", "[Merger]", "[ExtractAudio]", "[info]")):
            self._write("info", msg)

    def info(self, msg: str) -> None:
        self._write("info", msg)

    def warning(self, msg: str) -> None:
        self._write("warn", msg)

    def error(self, msg: str) -> None:
        self._write("error", msg)


def _progress_hook(log_path: Path):
    last_pct = {"value": -10.0}

    def hook(d: dict[str, Any]) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            if total:
                pct = downloaded * 100 / total
                if pct - last_pct["value"] >= 5:  # throttle: grava a cada 5% para não inchar o log
                    last_pct["value"] = pct
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"[progress] {pct:.0f}%\n")
                    except OSError:
                        pass
        elif d.get("status") == "finished":
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[progress] arquivo concluído: {d.get('filename', '')}\n")
            except OSError:
                pass

    return hook


def _base_opts(log_path: Path, cookiefile: Path | None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": False,
        "logger": _JobLogger(log_path),
        "progress_hooks": [_progress_hook(log_path)],
        "extractor_args": EXTRACTOR_ARGS_YOUTUBE,
        "noplaylist": True,
        "restrictfilenames": False,
    }
    if cookiefile is not None:
        opts["cookiefile"] = str(cookiefile)
    return opts


def download_video(url: str, output_dir: Path, log_path: Path, cookiefile: Path | None = None) -> None:
    """Baixa vídeo único, melhor vídeo+áudio, mesclado em .mp4."""
    opts = _base_opts(log_path, cookiefile)
    opts.update(
        {
            "outtmpl": str(output_dir / "%(title).150B [%(id)s].%(ext)s"),
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        }
    )
    _run(url, opts)


def download_audio(url: str, output_dir: Path, log_path: Path, cookiefile: Path | None = None) -> None:
    """Baixa só o áudio, convertido para .mp3 (192 kbps)."""
    opts = _base_opts(log_path, cookiefile)
    opts.update(
        {
            "outtmpl": str(output_dir / "%(title).150B [%(id)s].%(ext)s"),
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            ],
        }
    )
    _run(url, opts)


def download_playlist(
    url: str,
    output_dir: Path,
    log_path: Path,
    mode: str,
    cookiefile: Path | None = None,
) -> None:
    """Baixa uma playlist inteira como vídeo (.mp4) ou áudio (.mp3), um arquivo numerado por item."""
    opts = _base_opts(log_path, cookiefile)
    opts["noplaylist"] = False
    opts["yes_playlist"] = True
    # Sem isso, um único item indisponível (removido, privado, etc.) aborta a playlist
    # inteira em vez de pular pro próximo — equivalente a `-i`/`--ignore-errors` do yt-dlp.
    opts["ignoreerrors"] = True
    opts["outtmpl"] = str(output_dir / "%(playlist_index)s - %(title).150B [%(id)s].%(ext)s")
    if mode == "video":
        opts.update({"format": "bestvideo+bestaudio/best", "merge_output_format": "mp4"})
    else:
        opts.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                ],
            }
        )
    _run(url, opts)


def download_subtitles(
    url: str,
    output_dir: Path,
    log_path: Path,
    lang: str,
    auto: bool,
    cookiefile: Path | None = None,
) -> None:
    """Baixa só as legendas (manuais ou automáticas) no idioma escolhido, em .srt."""
    opts = _base_opts(log_path, cookiefile)
    opts.update(
        {
            "outtmpl": str(output_dir / "%(title).150B [%(id)s].%(ext)s"),
            "skip_download": True,
            "writesubtitles": not auto,
            "writeautomaticsub": auto,
            "subtitleslangs": [lang],
            "subtitlesformat": "srt",
            # Evita falhar só porque não há formatos de vídeo/áudio usáveis.
            "check_formats": "no",
            "ignore_no_formats_error": True,
        }
    )
    _run(url, opts)


def _run(url: str, opts: dict[str, Any]) -> None:
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)
        if "sign in to confirm" in msg.lower() or "cookies" in msg.lower():
            raise DownloadError(
                "O YouTube pediu confirmação anti-bot para esta URL. Envie um arquivo "
                "cookies.txt (exportado do navegador logado no YouTube, formato Netscape) "
                "no campo opcional do formulário e tente de novo."
            ) from exc
        raise DownloadError(f"Falha ao baixar: {msg}") from exc


def run_job(
    *,
    mode: str,
    url: str,
    output_dir: Path,
    log_path: Path,
    sub_lang: str = "pt",
    sub_auto: bool = False,
    cookiefile: Path | None = None,
) -> None:
    """Ponto único de entrada usado por jobs.py. Levanta DownloadError com mensagem amigável."""
    if mode not in VALID_MODES:
        raise DownloadError(f"Modo de download inválido: {mode}")
    if not url.strip():
        raise DownloadError("Informe a URL do vídeo ou playlist.")

    if mode == "video":
        download_video(url, output_dir, log_path, cookiefile)
    elif mode == "audio":
        download_audio(url, output_dir, log_path, cookiefile)
    elif mode == "playlist_video":
        download_playlist(url, output_dir, log_path, "video", cookiefile)
    elif mode == "playlist_audio":
        download_playlist(url, output_dir, log_path, "audio", cookiefile)
    elif mode == "subtitles":
        download_subtitles(url, output_dir, log_path, sub_lang, sub_auto, cookiefile)
