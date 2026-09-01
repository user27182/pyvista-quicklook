#!/bin/sh
# One-line installer for PyVista Quick Look. Safe to pipe from curl.
set -eu

REPO="${PVQL_REPO:-user27182/pyvista-quicklook}"
BRANCH="${PVQL_BRANCH:-main}"
SUPPORT="$HOME/Library/Application Support/PyVistaQuickLook"
SRC="${PVQL_SRC:-$SUPPORT/src}"
ASSET="PyVistaQuickLook.zip"

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = 'Darwin' ] || die 'PyVista Quick Look only runs on macOS.'

# Run from the checkout this script lives in when there is one, otherwise fetch it.
HERE=''
case "${0:-}" in
  */*) HERE=$(CDPATH='' cd -- "$(dirname -- "$0")/.." 2>/dev/null && pwd || true) ;;
esac

if [ -n "$HERE" ] && [ -x "$HERE/scripts/install.sh" ] && [ -d "$HERE/macos" ]; then
  ROOT="$HERE"
else
  say "==> downloading PyVista Quick Look into $SRC"
  rm -rf "$SRC"
  mkdir -p "$SRC"
  curl -LsSf "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" \
    | tar -xz -C "$SRC" --strip-components 1
  ROOT="$SRC"
fi

# A published build spares the reader a compiler; falling back to source needs one.
ZIP="${SUPPORT:?}/$ASSET"
UNPACKED="${SUPPORT:?}/unpacked"
APP=''
mkdir -p "$SUPPORT"
rm -rf "$ZIP" "$UNPACKED"

if curl -LsSf -o "$ZIP" "https://github.com/$REPO/releases/latest/download/$ASSET"; then
  say '==> unpacking the published app'
  mkdir -p "$UNPACKED"
  if ditto -x -k "$ZIP" "$UNPACKED"; then
    APP=$(find "$UNPACKED" -maxdepth 1 -name '*.app' -print -quit)
  fi
  rm -f "$ZIP"
fi

if [ -n "$APP" ] && [ -d "$APP" ]; then
  exec "$ROOT/scripts/install.sh" --app "$APP" "$@"
fi

say '==> no published build for this release; building from source'
exec "$ROOT/scripts/install.sh" "$@"
