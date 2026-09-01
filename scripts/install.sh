#!/usr/bin/env bash
# Install the pvql helper and its PyVista environment, build the app, and register it.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
APP_NAME="PyVistaQuickLook"
EXT_ID="io.github.user27182.PyVistaQuickLook.QuickLook"
SUPPORT="$HOME/Library/Application Support/PyVistaQuickLook"
VENV="$SUPPORT/venv"
DEST="$HOME/Applications"
PYTHON_VERSION="${PVQL_PYTHON:-3.12}"
# PyVista 0.49 is the floor and is not released yet.
PYVISTA_SPEC="${PVQL_PYVISTA_SPEC:-pyvista @ git+https://github.com/pyvista/pyvista.git}"
# SceneKit draws the previews, so only the reading half of the VTK fork is needed.
RUNTIME_DEPS=('cvista[io]' numpy pooch scooby typing-extensions)
PYVISTA=""
PYTHON=""
PREBUILT=""
SKIP_HELPER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) DEST="$2"; shift 2 ;;
    --pyvista) PYVISTA="$2"; shift 2 ;;
    --app) PREBUILT="$2"; shift 2 ;;
    --skip-helper) SKIP_HELPER=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# Only building needs a compiler; a prebuilt app is copied as it is.
if [[ -z "$PREBUILT" ]] && ! xcrun --find swiftc >/dev/null 2>&1; then
  echo "Xcode command line tools are needed to build the extension." >&2
  echo "Install them with:  xcode-select --install" >&2
  echo "Or install a prebuilt app with scripts/bootstrap.sh" >&2
  exit 1
fi

# uv provisions both the helper and the PyVista environment.
find_uv() {
  local candidate
  if candidate=$(command -v uv 2>/dev/null); then
    echo "$candidate"
    return
  fi
  for candidate in "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return
    fi
  done
}

UV=$(find_uv)
if [[ -z "$UV" ]]; then
  echo "==> installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV=$(find_uv)
  [[ -n "$UV" ]] || { echo "uv could not be installed" >&2; exit 1; }
fi

if [[ "$SKIP_HELPER" -eq 0 ]]; then
  echo "==> installing the pvql helper"
  "$UV" tool install --force --reinstall --quiet "$ROOT"
fi

HELPER=$(command -v pvql || echo "$HOME/.local/bin/pvql")
if [[ ! -x "$HELPER" ]]; then
  echo "pvql was not found after installation; expected at $HELPER" >&2
  exit 1
fi

# Without an explicit interpreter, keep PyVista in an environment of our own so the
# install never depends on what is already on this machine.
if [[ -z "$PYVISTA" ]]; then
  echo "==> preparing the PyVista environment in $VENV"
  echo "    (about 150 MB the first time)"
  mkdir -p "$SUPPORT"
  "$UV" venv --quiet --allow-existing --python "$PYTHON_VERSION" "$VENV"
  "$UV" pip install --quiet --python "$VENV/bin/python" --upgrade --no-deps "$PYVISTA_SPEC"
  "$UV" pip install --quiet --python "$VENV/bin/python" --upgrade "${RUNTIME_DEPS[@]}"
  PYTHON="$VENV/bin/python"
fi

if [[ -n "$PYVISTA" && ! -x "$PYVISTA" ]]; then
  echo "no pyvista executable at $PYVISTA" >&2
  exit 1
fi

echo "==> recording configuration"
if [[ -n "$PYVISTA" ]]; then
  "$HELPER" config --init --helper "$HELPER" --pyvista "$PYVISTA" >/dev/null
else
  "$HELPER" config --init --helper "$HELPER" --python "$PYTHON" >/dev/null
fi

echo "==> warming PyVista and VTK"
"$HELPER" warmup || echo "warm-up skipped; the first preview will be slower" >&2

echo "==> installing the render service"
"$HELPER" service --install --helper "$HELPER"

if [[ -n "$PREBUILT" ]]; then
  SOURCE_APP="$PREBUILT"
else
  "$ROOT/scripts/build.sh" --helper "$HELPER"
  SOURCE_APP="$ROOT/build/$APP_NAME.app"
fi

APP="$DEST/$APP_NAME.app"
echo "==> installing $APP"
mkdir -p "$DEST"
rm -rf "$APP"
cp -R "$SOURCE_APP" "$APP"

echo "==> registering with Launch Services and Quick Look"
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
"$LSREGISTER" -f -R -trusted "$APP"
/usr/bin/pluginkit -a "$APP/Contents/PlugIns/${APP_NAME}Extension.appex" 2>/dev/null || true
/usr/bin/pluginkit -e use -i "$EXT_ID" 2>/dev/null || true
/usr/bin/qlmanage -r >/dev/null 2>&1 || true
/usr/bin/qlmanage -r cache >/dev/null 2>&1 || true

echo
echo "Installed. Select a .vtu, .vtp, or .vtk file in the Finder and press space."
if ! command -v pvql >/dev/null 2>&1; then
  echo "The pvql command lives at $HELPER; add ~/.local/bin to PATH to use it by name."
fi
