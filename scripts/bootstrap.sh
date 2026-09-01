#!/bin/sh
# One-line installer for PyVista Quick Look. Safe to pipe from curl.
set -eu

REPO_URL="${PVQL_REPO:-https://github.com/user27182/pyvista-quicklook.git}"
BRANCH="${PVQL_BRANCH:-main}"
SUPPORT="$HOME/Library/Application Support/PyVistaQuickLook"
SRC="${PVQL_SRC:-$SUPPORT/src}"

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = 'Darwin' ] || die 'PyVista Quick Look only runs on macOS.'

if ! xcrun --find swiftc >/dev/null 2>&1; then
  die 'Xcode command line tools are needed to build the extension.
  Install them with:  xcode-select --install'
fi

# Run from the checkout this script lives in when there is one, otherwise fetch it.
HERE=''
case "${0:-}" in
  */*) HERE=$(CDPATH='' cd -- "$(dirname -- "$0")/.." 2>/dev/null && pwd || true) ;;
esac

if [ -n "$HERE" ] && [ -x "$HERE/scripts/install.sh" ] && [ -d "$HERE/macos" ]; then
  ROOT="$HERE"
else
  command -v git >/dev/null 2>&1 || die 'git is needed to download PyVista Quick Look.'
  mkdir -p "$SUPPORT"
  if [ -d "$SRC/.git" ]; then
    say "==> updating $SRC"
    git -C "$SRC" fetch --quiet --depth 1 origin "$BRANCH"
    git -C "$SRC" reset --quiet --hard "origin/$BRANCH"
  else
    say "==> downloading PyVista Quick Look into $SRC"
    git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$SRC"
  fi
  ROOT="$SRC"
fi

exec "$ROOT/scripts/install.sh" "$@"
