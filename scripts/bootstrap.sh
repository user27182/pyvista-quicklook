#!/bin/sh
# One-line installer for PyVista Quick Look. Safe to pipe from curl.
set -eu

REPO="${PVQL_REPO:-user27182/pyvista-quicklook}"
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

DOWNLOAD="https://github.com/$REPO/releases/latest/download/$ASSET"
if [ -n "$HERE" ] && [ -x "$HERE/scripts/install.sh" ] && [ -d "$HERE/macos" ]; then
  ROOT="$HERE"
else
  # The scripts and the app come from the same release, so the two never drift.
  TAG="${PVQL_TAG:-}"
  if [ -z "$TAG" ] && [ -z "${PVQL_BRANCH:-}" ]; then
    TAG=$(curl -sI "https://github.com/$REPO/releases/latest" | tr -d '\r' \
      | sed -n 's#^[Ll]ocation: .*/tag/##p')
  fi
  if [ -n "$TAG" ]; then
    ARCHIVE="https://github.com/$REPO/archive/refs/tags/$TAG.tar.gz"
    DOWNLOAD="https://github.com/$REPO/releases/download/$TAG/$ASSET"
    VERSION="${TAG#v}"
    say "==> installing PyVista Quick Look $TAG"
  else
    ARCHIVE="https://github.com/$REPO/archive/refs/heads/${PVQL_BRANCH:-main}.tar.gz"
    VERSION='0.0.0'
    say "==> no published release; installing from ${PVQL_BRANCH:-main}"
  fi
  say "==> downloading the installer into $SRC"
  rm -rf "$SRC"
  mkdir -p "$SRC"
  curl -LsSf "$ARCHIVE" | tar -xz -C "$SRC" --strip-components 1
  ROOT="$SRC"
  # A downloaded tarball carries no history for setuptools-scm to read.
  SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYVISTA_QUICKLOOK="${PVQL_VERSION:-$VERSION}"
  export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYVISTA_QUICKLOOK
fi

# A published build spares the reader a compiler; falling back to source needs one.
ZIP="${SUPPORT:?}/$ASSET"
UNPACKED="${SUPPORT:?}/unpacked"
APP=''
mkdir -p "$SUPPORT"
rm -rf "$ZIP" "$UNPACKED"

if curl -LsSf -o "$ZIP" "$DOWNLOAD"; then
  say '==> unpacking the published app'
  mkdir -p "$UNPACKED"
  if ditto -x -k "$ZIP" "$UNPACKED"; then
    APP=$(find "$UNPACKED" -maxdepth 1 -name '*.app' -print -quit)
  fi
  rm -f "$ZIP"
fi

if [ -n "$APP" ] && [ -d "$APP" ]; then
  "$ROOT/scripts/install.sh" --app "$APP" "$@" && outcome=0 || outcome=$?
else
  say '==> no published build for this release; building from source'
  "$ROOT/scripts/install.sh" "$@" && outcome=0 || outcome=$?
fi
# Nothing uses the downloads once the app and the helper are installed.
rm -rf "$UNPACKED"
[ "$ROOT" = "$SRC" ] && rm -rf "$SRC"
exit "$outcome"
