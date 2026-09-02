#!/usr/bin/env bash
# Install the pvql helper and its PyVista environment, build the app, and register it.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
APP_NAME="PyVistaQuickLook"
EXT_ID="io.github.user27182.PyVistaQuickLook.QuickLook"
SUPPORT="$HOME/Library/Application Support/PyVistaQuickLook"
VENV="$SUPPORT/venv"
DEST="$HOME/Applications"
# cvista's rendering wheels stop at 3.12.
PYTHON_VERSION="${PVQL_PYTHON:-3.12}"
# PyVista 0.49 is the floor and is not released yet. The commit matches pyproject.toml;
# the io extra brings meshio and pyvista-zstd, whichever readers PyVista routes to them.
PYVISTA_SPEC="${PVQL_PYVISTA_SPEC:-pyvista[io] @ git+https://github.com/pyvista/pyvista.git@f96cb9990ec77ba0d12d4d19cba6035e6b1841aa}"
# STEP, DXF, and 3MF readers; IGES and the heavier CAD kernels need stock VTK or OCP.
CAD_SPEC="${PVQL_CAD_SPEC:-pyvista-cad[step-light,3mf]}"
PYTHON=""
PREBUILT=""
SKIP_HELPER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) DEST="$2"; shift 2 ;;
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

# PyVista lives in an environment of its own, so the install never depends on what is
# already on this machine.
echo "==> preparing the PyVista environment in $VENV"
echo "    (about 400 MB the first time)"
mkdir -p "$SUPPORT"
"$UV" venv --quiet --allow-existing --python "$PYTHON_VERSION" "$VENV"
# PyVista requires stock VTK, which cvista replaces; the override drops that requirement.
# uv splits the override path on spaces, so the file cannot live in Application Support.
OVERRIDES=$(mktemp -t pvql-overrides)
printf "vtk; python_version < '0'\n" > "$OVERRIDES"
"$UV" pip uninstall --quiet --python "$VENV/bin/python" vtk >/dev/null 2>&1 || true
"$UV" pip install --quiet --python "$VENV/bin/python" --upgrade \
  --override "$OVERRIDES" "$PYVISTA_SPEC" 'cvista[all]' "$CAD_SPEC"
rm -f "$OVERRIDES"
PYTHON="$VENV/bin/python"

echo "==> recording configuration"
"$HELPER" config --init --helper "$HELPER" --python "$PYTHON" >/dev/null

echo "==> warming PyVista and VTK"
"$HELPER" warmup || echo "warm-up skipped; the first preview will be slower" >&2

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

# After the app, so macOS lists the service under the app's name.
echo "==> installing the render service"
"$HELPER" service --install --helper "$HELPER"

echo
echo "Installed. Select a .vtu, .vtp, or .vtk file in the Finder and press space."
if ! command -v pvql >/dev/null 2>&1; then
  echo "The pvql command lives at $HELPER; add ~/.local/bin to PATH to use it by name."
fi
