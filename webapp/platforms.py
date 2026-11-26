"""
Identifica de qual plataforma é a URL, pra ajustar nomes de arquivo, formatos, mensagens de erro e
os modos disponíveis. Qualquer outro site continua indo pro yt-dlp com o comportamento genérico.
"""

from __future__ import annotations

from urllib.parse import urlsplit

YOUTUBE = "youtube"
INSTAGRAM = "instagram"
OTHER = "other"

_DOMAINS = {
    YOUTUBE: ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    INSTAGRAM: ("instagram.com",),
}


def detect_platform(url: str) -> str:
    """Compara o host exato (ou subdomínio), nunca um trecho solto da URL."""
    url = (url or "").strip()
    if "://" not in url:
        url = "https://" + url
    try:
        host = (urlsplit(url).hostname or "").rstrip(".")
    except ValueError:
        return OTHER
    for platform, domains in _DOMAINS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return platform
    return OTHER
