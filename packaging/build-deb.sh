#!/usr/bin/env bash
# Monta o pacote .deb do Tube Fetch Desktop a partir do onedir já gerado pelo PyInstaller
# (dist/tube-fetch-desktop/, via packaging/tube-fetch-desktop-linux.spec).
#
# Uso (a partir da raiz do repositório):
#   packaging/build-deb.sh <APP_VERSION> [dist_dir] [output_dir]
#
# Ex.: packaging/build-deb.sh 2026.08.18-abc1234
set -euo pipefail

APP_VERSION="${1:?uso: build-deb.sh <APP_VERSION> [dist_dir] [output_dir]}"
DIST_DIR="${2:-dist/tube-fetch-desktop}"
OUTPUT_DIR="${3:-packaging/Output}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

if [ ! -d "$DIST_DIR" ]; then
  echo "erro: dist_dir '$DIST_DIR' não existe (rode o PyInstaller primeiro)" >&2
  exit 1
fi

PKG_ROOT="$STAGE_DIR/tube-fetch-desktop"
mkdir -p "$PKG_ROOT/DEBIAN" \
         "$PKG_ROOT/opt/tube-fetch-desktop" \
         "$PKG_ROOT/usr/bin" \
         "$PKG_ROOT/usr/share/applications"

cp -a "$DIST_DIR"/. "$PKG_ROOT/opt/tube-fetch-desktop/"
chmod +x "$PKG_ROOT/opt/tube-fetch-desktop/tube-fetch-desktop"

ln -s /opt/tube-fetch-desktop/tube-fetch-desktop "$PKG_ROOT/usr/bin/tube-fetch-desktop"

cp "$ROOT_DIR/packaging/debian/tube-fetch-desktop.desktop" \
   "$PKG_ROOT/usr/share/applications/tube-fetch-desktop.desktop"

sed "s/__APP_VERSION__/${APP_VERSION}/" "$ROOT_DIR/packaging/debian/control.template" \
  > "$PKG_ROOT/DEBIAN/control"

case "$OUTPUT_DIR" in
  /*) ;;
  *) OUTPUT_DIR="$ROOT_DIR/$OUTPUT_DIR" ;;
esac
mkdir -p "$OUTPUT_DIR"
DEB_PATH="$OUTPUT_DIR/tube-fetch-desktop_${APP_VERSION}_amd64.deb"

dpkg-deb --build --root-owner-group "$PKG_ROOT" "$DEB_PATH"

echo "Gerado: $DEB_PATH"
