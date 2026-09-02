#!/usr/bin/env bash
# Remove the app, its Quick Look registration, the render service, and the cached previews.
set -euo pipefail

APP_NAME="PyVistaQuickLook"
LABEL="io.github.user27182.pvqld"
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

for candidate in "$HOME/Applications/$APP_NAME.app" "/Applications/$APP_NAME.app"; do
  if [[ -d "$candidate" ]]; then
    echo "==> removing $candidate"
    /usr/bin/pluginkit -r "$candidate/Contents/PlugIns/${APP_NAME}Extension.appex" 2>/dev/null || true
    "$LSREGISTER" -u "$candidate" >/dev/null 2>&1 || true
    rm -rf "$candidate"
  fi
done

# The service is removed by label, so it goes even when pvql is no longer on PATH.
echo "==> removing the render service"
/bin/launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"

/usr/bin/qlmanage -r >/dev/null 2>&1 || true
/usr/bin/qlmanage -r cache >/dev/null 2>&1 || true

SUPPORT="$HOME/Library/Application Support/PyVistaQuickLook"
rm -rf "$HOME/Library/Caches/PyVistaQuickLook" "$SUPPORT/venv" "$SUPPORT/src" "$SUPPORT/unpacked" "$SUPPORT/overrides.txt"
echo "removed the app, the render service, the cache, the PyVista environment, and the download"
echo "the config file was left at $SUPPORT/config.json"
echo "remove the helper with:  uv tool uninstall pyvista-quicklook"
