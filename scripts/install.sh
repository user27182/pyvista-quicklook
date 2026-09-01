#!/usr/bin/env bash
# Install the pvql helper, build the app, and register it with Quick Look.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
APP_NAME="PyVistaQuickLook"
EXT_ID="io.github.user27182.PyVistaQuickLook.QuickLook"
DEST="$HOME/Applications"
PYVISTA=""
SKIP_HELPER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) DEST="$2"; shift 2 ;;
    --pyvista) PYVISTA="$2"; shift 2 ;;
    --skip-helper) SKIP_HELPER=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ "$SKIP_HELPER" -eq 0 ]]; then
  echo "==> installing the pvql helper"
  if command -v uv >/dev/null 2>&1; then
    uv tool install --force --reinstall "$ROOT"
  else
    python3 -m pip install --user --upgrade "$ROOT"
  fi
fi

HELPER=$(command -v pvql || echo "$HOME/.local/bin/pvql")
if [[ ! -x "$HELPER" ]]; then
  echo "pvql was not found after installation; expected at $HELPER" >&2
  exit 1
fi

echo "==> recording configuration"
if [[ -n "$PYVISTA" ]]; then
  "$HELPER" config --init --helper "$HELPER" --pyvista "$PYVISTA" >/dev/null
else
  "$HELPER" config --init --helper "$HELPER" >/dev/null
fi

echo "==> installing the render service"
"$HELPER" service --install --helper "$HELPER"

"$ROOT/scripts/build.sh" --helper "$HELPER"

APP="$DEST/$APP_NAME.app"
echo "==> installing $APP"
mkdir -p "$DEST"
rm -rf "$APP"
cp -R "$ROOT/build/$APP_NAME.app" "$APP"

echo "==> registering with Launch Services and Quick Look"
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
"$LSREGISTER" -f -R -trusted "$APP"
/usr/bin/pluginkit -a "$APP/Contents/PlugIns/${APP_NAME}Extension.appex" 2>/dev/null || true
/usr/bin/pluginkit -e use -i "$EXT_ID" 2>/dev/null || true
/usr/bin/qlmanage -r >/dev/null 2>&1 || true
/usr/bin/qlmanage -r cache >/dev/null 2>&1 || true

echo "==> warming PyVista and VTK"
"$HELPER" warmup || echo "warm-up skipped; the first preview will be slower" >&2

echo
echo "installed. Verify with:"
echo "    pvql doctor"
