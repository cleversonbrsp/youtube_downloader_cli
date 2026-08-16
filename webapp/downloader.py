"""
Núcleo de download com yt-dlp: vídeo, áudio, playlist (vídeo/áudio) e legendas.

Adaptado do CLI original (youtube_downloader_cli/main.py) para rodar dentro de um job de
background (ver jobs.py): nada de prompts interativos — todos os parâmetros chegam explícitos
do formulário web, e as mensagens do yt-dlp vão para um arquivo de log por job (lido pela UI).
"""

from __future__ import annotations

import re
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


# Linha típica que o yt-dlp manda pro logger quando um item de playlist falha, ex.:
# "ERROR: [youtube] Ss0kFNUP4P4: Video unavailable. It was removed following a copyright
# removal request by SME" — capturamos o id do vídeo e o motivo cru pra traduzir depois.
_ITEM_ERROR_RE = re.compile(r"^(?:ERROR:\s*)?\[youtube\]\s+([A-Za-z0-9_-]{11}):\s*(.+)$")
# "[youtube:tab] YouTube said: INFO - 10 unavailable videos are hidden" — vídeos que o próprio
# YouTube já tira da listagem da playlist antes do yt-dlp tentar baixar (sem id individual).
_HIDDEN_COUNT_RE = re.compile(r"(\d+)\s+unavailable videos are hidden")


def _friendly_reason(raw: str) -> str:
    """Traduz o motivo cru do yt-dlp pra uma frase que explica pro usuário por que não baixou."""
    low = raw.lower()
    if "copyright removal request" in low:
        m = re.search(r"\bby ([A-Za-z0-9 .&-]+?)\.?$", raw)
        quem = m.group(1).strip() if m else None
        return (
            f"Removido do YouTube por reclamação de direitos autorais de {quem}."
            if quem
            else "Removido do YouTube por reclamação de direitos autorais."
        )
    if "private video" in low:
        return "Vídeo privado — o dono não deixou público."
    if "account associated with this video has been terminated" in low:
        return "O canal foi encerrado pelo YouTube."
    if "removed by the uploader" in low:
        return "Removido pelo próprio autor do vídeo."
    if "not available in your country" in low or "blocked it in your country" in low:
        return "Bloqueado por região — indisponível a partir do seu país."
    if "members-only" in low or "join this channel" in low:
        return "Conteúdo exclusivo para membros do canal (assinatura paga)."
    if "sign in to confirm your age" in low or ("age" in low and "confirm" in low):
        return "Restrito por idade — envie um cookies.txt (usuário logado) e tente de novo."
    if "video unavailable" in low:
        return "Vídeo indisponível no YouTube (removido ou nunca existiu)."
    return raw


class _JobLogger:
    """Recebe as mensagens do yt-dlp (objeto `logger`) e grava num arquivo de log por job."""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self.skipped: list[dict[str, Any]] = []
        self.hidden_count = 0
        self._seen_ids: set[str] = set()
        # Preenchido por download_playlist() antes do download de verdade começar — a mensagem
        # de erro do yt-dlp só traz o id do vídeo, não o título nem a posição na playlist.
        self.playlist_index: dict[str, dict[str, Any]] = {}

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
        m = _HIDDEN_COUNT_RE.search(msg)
        if m:
            self.hidden_count = max(self.hidden_count, int(m.group(1)))

    def error(self, msg: str) -> None:
        self._write("error", msg)
        m = _ITEM_ERROR_RE.match(msg.strip())
        if m:
            video_id, reason = m.group(1), m.group(2)
            if video_id not in self._seen_ids:
                self._seen_ids.add(video_id)
                meta = self.playlist_index.get(video_id, {})
                self.skipped.append(
                    {
                        "id": video_id,
                        "index": meta.get("index"),
                        "title": meta.get("title"),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "reason": _friendly_reason(reason),
                    }
                )


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


def download_video(
    url: str, output_dir: Path, log_path: Path, cookiefile: Path | None = None
) -> list[dict[str, Any]]:
    """Baixa vídeo único, melhor vídeo+áudio, mesclado em .mp4."""
    opts = _base_opts(log_path, cookiefile)
    opts.update(
        {
            "outtmpl": str(output_dir / "%(title).150B [%(id)s].%(ext)s"),
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        }
    )
    return _run(url, opts)


def download_audio(
    url: str, output_dir: Path, log_path: Path, cookiefile: Path | None = None
) -> list[dict[str, Any]]:
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
    return _run(url, opts)


def _flat_playlist_index(url: str, cookiefile: Path | None) -> dict[str, dict[str, Any]]:
    """Lista os itens da playlist sem baixar nada (extract_flat), só pra saber título e posição
    de cada vídeo antes da tentativa real — a mensagem de erro do yt-dlp num item que falha só
    traz o id, e nessa altura a extração completa (que traria o título) já não rolou.
    Enriquecimento best-effort: qualquer falha aqui é engolida e os itens que falharem depois
    ficam só com id/motivo, sem título/posição — nunca derruba o job por causa disso."""
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "extractor_args": EXTRACTOR_ARGS_YOUTUBE,
    }
    if cookiefile is not None:
        opts["cookiefile"] = str(cookiefile)

    index: dict[str, dict[str, Any]] = {}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:  # noqa: BLE001
        return index

    for pos, entry in enumerate((info or {}).get("entries") or [], start=1):
        if not entry:
            continue
        video_id = entry.get("id")
        if not video_id:
            continue
        index[video_id] = {"index": entry.get("playlist_index") or pos, "title": entry.get("title")}
    return index


def download_playlist(
    url: str,
    output_dir: Path,
    log_path: Path,
    mode: str,
    cookiefile: Path | None = None,
) -> list[dict[str, Any]]:
    """Baixa uma playlist inteira como vídeo (.mp4) ou áudio (.mp3), um arquivo numerado por item."""
    playlist_index = _flat_playlist_index(url, cookiefile)

    opts = _base_opts(log_path, cookiefile)
    opts["noplaylist"] = False
    opts["yes_playlist"] = True
    # Sem isso, um único item indisponível (removido, privado, etc.) aborta a playlist
    # inteira em vez de pular pro próximo — equivalente a `-i`/`--ignore-errors` do yt-dlp.
    opts["ignoreerrors"] = True
    opts["outtmpl"] = str(output_dir / "%(playlist_index)s - %(title).150B [%(id)s].%(ext)s")
    opts["logger"].playlist_index = playlist_index
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
    return _run(url, opts)


def download_subtitles(
    url: str,
    output_dir: Path,
    log_path: Path,
    lang: str,
    auto: bool,
    cookiefile: Path | None = None,
) -> list[dict[str, Any]]:
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
    return _run(url, opts)


def _run(url: str, opts: dict[str, Any]) -> list[dict[str, Any]]:
    logger: _JobLogger = opts["logger"]
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

    skipped = list(logger.skipped)
    if logger.hidden_count:
        skipped.append(
            {
                "id": None,
                "index": None,
                "title": None,
                "url": None,
                "reason": (
                    f"{logger.hidden_count} vídeo(s) da playlist já apareciam como indisponíveis "
                    "(removidos/privados) pro próprio YouTube antes mesmo do download começar."
                ),
            }
        )
    return skipped


def run_job(
    *,
    mode: str,
    url: str,
    output_dir: Path,
    log_path: Path,
    sub_lang: str = "pt",
    sub_auto: bool = False,
    cookiefile: Path | None = None,
) -> list[dict[str, Any]]:
    """Ponto único de entrada usado por jobs.py. Levanta DownloadError com mensagem amigável.

    Retorna a lista de itens de playlist pulados (id + motivo amigável), vazia fora do modo
    playlist ou quando nada foi pulado.
    """
    if mode not in VALID_MODES:
        raise DownloadError(f"Modo de download inválido: {mode}")
    if not url.strip():
        raise DownloadError("Informe a URL do vídeo ou playlist.")

    if mode == "video":
        return download_video(url, output_dir, log_path, cookiefile)
    elif mode == "audio":
        return download_audio(url, output_dir, log_path, cookiefile)
    elif mode == "playlist_video":
        return download_playlist(url, output_dir, log_path, "video", cookiefile)
    elif mode == "playlist_audio":
        return download_playlist(url, output_dir, log_path, "audio", cookiefile)
    else:
        return download_subtitles(url, output_dir, log_path, sub_lang, sub_auto, cookiefile)
