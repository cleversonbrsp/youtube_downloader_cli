"""
Ponto de entrada do executável Windows: sobe o servidor local (Waitress) numa janela própria
do aplicativo (pywebview), em vez de abrir uma aba do navegador.

Desenvolvido por Cleverson Rodrigues.

Quando empacotado pelo PyInstaller (modo --onedir, sem console — ver packaging/tube-fetch-desktop.spec),
os arquivos de dados (templates/, static/) e os binários bundlados (ffmpeg.exe, deno.exe) ficam na
mesma pasta do .exe — adiciona essa pasta ao PATH para o yt-dlp/ffmpeg encontrarem os binários
sem configuração extra.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from threading import Thread

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))
os.environ["PATH"] = str(BASE_DIR) + os.pathsep + os.environ.get("PATH", "")

PORT = int(os.environ.get("TUBEFETCH_DESKTOP_PORT", "5000"))
URL = f"http://127.0.0.1:{PORT}/"
WINDOW_TITLE = "Tube Fetch Desktop — por Cleverson Rodrigues"


def _notify(message: str) -> None:
    """Mostra um aviso ao usuário: caixa de diálogo nativa no Windows (sem console visível
    para ler um print), ou stdout em outros sistemas / ao rodar a partir do código-fonte."""
    print(message)
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "Tube Fetch Desktop", 0x40)  # MB_ICONINFORMATION
        except Exception:  # noqa: BLE001
            pass


def _serve() -> None:
    from waitress import serve

    import app as flask_app_module

    serve(flask_app_module.app, host="127.0.0.1", port=PORT)


def _wait_until_ready(timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(URL + "health", timeout=1) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.15)
    return False


def main() -> None:
    Thread(target=_serve, daemon=True).start()
    if not _wait_until_ready():
        _notify(
            "O servidor local do Tube Fetch Desktop não respondeu a tempo.\n"
            "Feche e tente abrir o aplicativo de novo."
        )
        return

    try:
        import webview

        webview.create_window(
            WINDOW_TITLE,
            URL,
            width=1180,
            height=860,
            min_size=(760, 560),
            text_select=True,
        )
        # No Windows, força o WebView2 (Edge Chromium) — motor moderno, mesmo CSS/JS testado no
        # navegador. Sem o runtime do WebView2 instalado, isto levanta uma exceção tratada abaixo.
        webview.start(gui="edgechromium" if sys.platform == "win32" else None, private_mode=False)
    except Exception as exc:  # noqa: BLE001 — qualquer falha de GUI cai para o navegador padrão
        _notify(
            "Não foi possível abrir a janela própria do Tube Fetch Desktop "
            f"({exc}).\n\nIsso costuma significar que o WebView2 Runtime não está instalado "
            "(o Windows Update normalmente já instala isso sozinho).\n\n"
            "Abrindo no seu navegador padrão em http://127.0.0.1:5000 em vez disso — "
            "a aplicação continua funcionando normalmente."
        )
        webbrowser.open(URL)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
