# -*- mode: python ; coding: utf-8 -*-
"""
Spec do PyInstaller para o Tube Fetch Desktop (Windows).

Empacota launcher.py (que sobe o Flask via Waitress e abre o navegador) + templates/static +
ffmpeg.exe e deno.exe (baixados antes deste passo pelo workflow build-windows.yml em
build/bin/). Modo --onedir (não --onefile): mais confiável para bundlar binários grandes como o
ffmpeg e evita falsos positivos de antivírus comuns em onefile self-extracting.

Rodar a partir da raiz do repositório:
    pyinstaller packaging/tube-fetch-desktop.spec --noconfirm
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - SPECPATH é injetado pelo PyInstaller
WEBAPP = ROOT / "webapp"
BIN_DIR = ROOT / "build" / "bin"

binaries = []
for exe_name in ("ffmpeg.exe", "deno.exe"):
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
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "clr_loader",
        "clr",
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
    name="TubeFetchDesktop",
    # Sem janela de console: é um app com janela própria (pywebview), não um script de terminal.
    # Erros de inicialização viram uma caixa de diálogo nativa (ver launcher.py), não texto no
    # console — por isso console=False não esconde nenhuma mensagem importante do usuário.
    console=False,
    icon=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="TubeFetchDesktop",
)
