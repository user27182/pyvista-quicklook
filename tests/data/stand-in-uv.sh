#!/bin/sh
# A uv for the installer tests, configured by the STAND_IN_* variables.
printf '%s\n' "$*" >> "$STAND_IN_LOG"
case "$1" in
  --version) echo "uv $(cat "$STAND_IN_VERSION")" ;;
  self)
    if [ -n "$STAND_IN_UPDATE_TO" ]; then
      echo "$STAND_IN_UPDATE_TO" > "$STAND_IN_VERSION"
    else
      echo "error: cannot self-update this uv" >&2
      exit 2
    fi ;;
  pip)
    previous=
    for argument in "$@"; do
      if [ "$previous" = --excludes ]; then cat "$argument" > "$STAND_IN_EXCLUDES"; fi
      previous=$argument
    done ;;
esac
