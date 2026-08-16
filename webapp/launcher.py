"""
Ponto de entrada do executável Windows: sobe o servidor local (Waitress) e abre o navegador.

Quando empacotado pelo PyInstaller (modo --onedir), os arquivos de dados (templates/, static/)
e os binários bundlados (ffmpeg.exe, deno.exe) ficam na mesma pasta do .exe — adiciona essa
pasta ao PATH para o yt-dlp/ffmpeg encontrarem os binários sem configuração extra.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path
from threading import Timer

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))
os.environ["PATH"] = str(BASE_DIR) + os.pathsep + os.environ.get("PATH", "")

PORT = int(os.environ.get("TUBEFETCH_DESKTOP_PORT", "5000"))


def _open_browser() -> None:
    webbrowser.open(f"http://127.0.0.1:{PORT}/")


def main() -> None:
    from waitress import serve

    import app as flask_app_module

    print("=" * 60)
    print(" Tube Fetch Desktop")
    print(f" Rodando em http://127.0.0.1:{PORT}")
    print(" Feche esta janela (ou Ctrl+C) para encerrar o servidor.")
    print("=" * 60)

    Timer(1.2, _open_browser).start()
    serve(flask_app_module.app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
