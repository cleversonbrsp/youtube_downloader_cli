# -*- mode: python ; coding: utf-8 -*-
"""
Spec do PyInstaller para o Tube Fetch Desktop (Linux).

Irmão de tube-fetch-desktop.spec (Windows): empacota launcher.py + templates/static + os
binários ffmpeg e deno (baixados antes deste passo pelo workflow build-linux.yml em
build/bin/, sem extensão .exe). Modo --onedir pelos mesmos motivos do spec Windows.

GTK/WebKit2 (motor da janela do pywebview no Linux) NÃO são bundlados aqui — ficam a cargo do
sistema (pacotes Depends do .deb: veja packaging/debian/control), porque são bibliotecas do
sistema fortemente acopladas à versão da distro; embutir a cópia da máquina de build causaria
incompatibilidade em outras versões do Ubuntu/Debian. O binário PyGObject (o módulo `gi`) é
instalado via pip contra os headers do sistema no CI e É bundlado normalmente.

Rodar a partir da raiz do repositório:
    pyinstaller packaging/tube-fetch-desktop-linux.spec --noconfirm
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - SPECPATH é injetado pelo PyInstaller
WEBAPP = ROOT / "webapp"
BIN_DIR = ROOT / "build" / "bin"

binaries = []
for exe_name in ("ffmpeg", "deno"):
    exe_path = BIN_DIR / exe_name
    if exe_path.is_file():
        binaries.append((str(exe_path), "."))

a = Analysis(  # noqa: F821
    [str(WEBAPP / "launcher.py")],
    pathex=[str(WEBAPP)],
    binaries=binaries,
    datas=[
        (str(WEBAPP / "templates"), "templates"),
        (str(WEBAPP / "static"), "static"),
    ],
    hiddenimports=[
        "waitress",
        "webview.platforms.gtk",
        "gi",
        "gi.repository.Gtk",
        "gi.repository.Gio",
        "gi.repository.GLib",
        "gi.repository.WebKit2",
    ],
    hookspath=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="tube-fetch-desktop",
    console=False,
    icon=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="tube-fetch-desktop",
)
