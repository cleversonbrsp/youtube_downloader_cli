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
import shutil
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


class Api:
    """Ponte JS -> Python exposta na janela (window.pywebview.api.*).

    Existe porque, dentro do WebView2 embutido, um <a href> apontando para um arquivo com
    Content-Disposition: attachment não dispara o diálogo "Salvar como" do Windows (funciona
    num navegador normal, mas não aqui) — o clique simplesmente não faz nada. Em vez de
    depender do navegador embutido para isso, o botão "Baixar" chama estes métodos, que abrem
    o diálogo nativo de salvar e copiam o arquivo diretamente do disco (mesma máquina, sem
    precisar passar pelo HTTP de novo).
    """

    def _save_path(self, job_id: str, token: str, filename: str):
        import jobs

        rec, err = jobs.get_job(job_id, token)
        if err:
            return None, err
        path = jobs.resolve_job_file(job_id, filename)
        if path is None:
            return None, "Arquivo não encontrado."
        return path, None

    def save_job_file(self, job_id: str, token: str, filename: str) -> dict:
        import webview

        path, err = self._save_path(job_id, token, filename)
        if err:
            return {"ok": False, "error": err}

        window = webview.windows[0]
        result = window.create_file_dialog(webview.FileDialog.SAVE, save_filename=path.name)
        if not result:
            return {"ok": False, "error": None}  # usuário cancelou o diálogo

        dest = result[0] if isinstance(result, (list, tuple)) else result
        try:
            shutil.copy2(path, dest)
        except OSError as e:
            return {"ok": False, "error": f"Não foi possível salvar: {e}"}
        return {"ok": True, "path": str(dest)}

    def save_job_zip(self, job_id: str, token: str) -> dict:
        import webview

        import jobs

        rec, err = jobs.get_job(job_id, token)
        if err:
            return {"ok": False, "error": err}
        zip_path = jobs.build_zip(job_id)
        if zip_path is None:
            return {"ok": False, "error": "Nenhum arquivo para compactar."}

        window = webview.windows[0]
        result = window.create_file_dialog(webview.FileDialog.SAVE, save_filename=f"tube-fetch-{job_id[:8]}.zip")
        if not result:
            return {"ok": False, "error": None}

        dest = result[0] if isinstance(result, (list, tuple)) else result
        try:
            shutil.copy2(zip_path, dest)
        except OSError as e:
            return {"ok": False, "error": f"Não foi possível salvar: {e}"}
        return {"ok": True, "path": str(dest)}

    def choose_download_dir(self) -> dict:
        """Abre o diálogo nativo de escolha de pasta. O caller manda esse caminho de volta em
        POST /api/jobs (campo dest_dir) — o job baixa direto lá, sem passar pela pasta efêmera
        do job nem precisar de um "Salvar" por arquivo."""
        import webview

        window = webview.windows[0]
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return {"ok": False, "path": None}  # usuário cancelou o diálogo
        path = result[0] if isinstance(result, (list, tuple)) else result
        return {"ok": True, "path": str(path)}


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
            js_api=Api(),
        )
        # No Windows, força o WebView2 (Edge Chromium) — motor moderno, mesmo CSS/JS testado no
        # navegador. Sem o runtime do WebView2 instalado, isto levanta uma exceção tratada abaixo.
        # No Linux, deixa o pywebview escolher (normalmente GTK+WebKit2, instalado via Depends
        # do .deb — ver packaging/debian/control); sem esses pacotes, cai na mesma exceção.
        webview.start(gui="edgechromium" if sys.platform == "win32" else None, private_mode=False)
    except Exception as exc:  # noqa: BLE001 — qualquer falha de GUI cai para o navegador padrão
        if sys.platform == "win32":
            reason = (
                "Isso costuma significar que o WebView2 Runtime não está instalado "
                "(o Windows Update normalmente já instala isso sozinho)."
            )
        elif sys.platform.startswith("linux"):
            reason = (
                "Isso costuma significar que os pacotes GTK/WebKit2 do sistema não estão "
                "instalados (deveriam ter vindo automaticamente com o pacote .deb)."
            )
        else:
            reason = "Isso costuma significar que o motor de janela nativo não está disponível neste sistema."
        _notify(
            f"Não foi possível abrir a janela própria do Tube Fetch Desktop ({exc}).\n\n{reason}\n\n"
            "Abrindo no seu navegador padrão em http://127.0.0.1:5000 em vez disso — "
            "a aplicação continua funcionando normalmente."
        )
        webbrowser.open(URL)
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
