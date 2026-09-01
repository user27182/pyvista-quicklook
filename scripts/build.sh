#!/usr/bin/env bash
# Build PyVistaQuickLook.app with its Quick Look extension embedded.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BUILD="$ROOT/build"
APP_NAME="PyVistaQuickLook"
EXT_NAME="PyVistaQuickLookExtension"
APP_ID="io.github.user27182.PyVistaQuickLook"
EXT_ID="$APP_ID.QuickLook"
DEPLOYMENT_TARGET="12.0"

HELPER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --helper) HELPER="$2"; shift 2 ;;
    --output) BUILD="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$HELPER" ]]; then
  HELPER=$(command -v pvql || true)
fi
if [[ -z "$HELPER" ]]; then
  HELPER="$HOME/.local/bin/pvql"
fi

APP="$BUILD/$APP_NAME.app"
APPEX="$APP/Contents/PlugIns/$EXT_NAME.appex"
TARGET="$(uname -m)-apple-macos$DEPLOYMENT_TARGET"

echo "==> cleaning $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$APPEX/Contents/MacOS"

echo "==> generating Info.plist files (helper: $HELPER)"
PYTHONPATH="$ROOT/src" python3 -m pvql plist \
  --app "$APP/Contents/Info.plist" \
  --extension "$APPEX/Contents/Info.plist" \
  --helper "$HELPER" >/dev/null
printf 'APPL????' > "$APP/Contents/PkgInfo"
printf 'XPC!????' > "$APPEX/Contents/PkgInfo"

echo "==> compiling $APP_NAME"
swiftc -target "$TARGET" -O \
  "$ROOT/macos/Shared/Helper.swift" \
  "$ROOT/macos/App/main.swift" \
  -o "$APP/Contents/MacOS/$APP_NAME" \
  -framework AppKit

echo "==> compiling $EXT_NAME"
swiftc -target "$TARGET" -O -parse-as-library \
  "$ROOT/macos/Shared/Helper.swift" \
  "$ROOT/macos/QuickLookExtension/PreviewProvider.swift" \
  -o "$APPEX/Contents/MacOS/$EXT_NAME" \
  -framework QuickLookUI \
  -Xlinker -e -Xlinker _NSExtensionMain

echo "==> signing"
codesign --force --sign - --identifier "$EXT_ID" --timestamp=none \
  --entitlements "$ROOT/macos/QuickLookExtension/QuickLook.entitlements" "$APPEX"
codesign --force --sign - --identifier "$APP_ID" --timestamp=none "$APP"
codesign --verify --deep --strict "$APP"

echo "built $APP"
