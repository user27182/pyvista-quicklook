#!/usr/bin/env bash
# Remove the app, its Quick Look registration, and the cached previews.
set -euo pipefail

APP_NAME="PyVistaQuickLook"

for candidate in "$HOME/Applications/$APP_NAME.app" "/Applications/$APP_NAME.app"; do
  if [[ -d "$candidate" ]]; then
    echo "==> removing $candidate"
    /usr/bin/pluginkit -r "$candidate/Contents/PlugIns/${APP_NAME}Extension.appex" 2>/dev/null || true
    rm -rf "$candidate"
  fi
done

if command -v pvql >/dev/null 2>&1; then
  echo "==> removing the render service"
  pvql service --uninstall || true
fi

LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
"$LSREGISTER" -kill -r -domain local -domain system -domain user >/dev/null 2>&1 || true
/usr/bin/qlmanage -r >/dev/null 2>&1 || true
/usr/bin/qlmanage -r cache >/dev/null 2>&1 || true

SUPPORT="$HOME/Library/Application Support/PyVistaQuickLook"
rm -rf "$HOME/Library/Caches/PyVistaQuickLook" "$SUPPORT/venv" "$SUPPORT/src"
echo "removed the app, its cache, the PyVista environment, and the downloaded source"
echo "the config file was left at $SUPPORT/config.json"
echo "remove the helper with:  uv tool uninstall pyvista-quicklook"
