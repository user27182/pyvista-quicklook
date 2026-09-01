"""Configuration loading for the Quick Look helper."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Any

APP_SUPPORT = Path.home() / 'Library' / 'Application Support' / 'PyVistaQuickLook'
CONFIG_PATH = APP_SUPPORT / 'config.json'
CACHE_DIR = Path.home() / 'Library' / 'Caches' / 'PyVistaQuickLook'
LOG_PATH = APP_SUPPORT / 'pvql.log'

DEFAULTS: dict[str, Any] = {
    'pyvista': None,
    'pvql': None,
    'window_size': [1024, 1024],
    'timeout': 60,
    'max_file_size_mb': 512,
    'background': None,
    'extra_args': [],
    'extensions': {'add': [], 'remove': []},
    'cache': True,
    'log': False,
}

# Interpreters searched when ``pyvista`` is not set in the config file.
_CANDIDATE_DIRS = (
    Path.home() / '.local' / 'bin',
    Path('/opt/homebrew/bin'),
    Path('/usr/local/bin'),
)


def load() -> dict[str, Any]:
    """Return the merged configuration, falling back to defaults."""
    config = json.loads(json.dumps(DEFAULTS))
    if CONFIG_PATH.is_file():
        try:
            user = json.loads(CONFIG_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            user = {}
        if isinstance(user, dict):
            config.update({k: v for k, v in user.items() if k in DEFAULTS})
    config['extensions'] = {**DEFAULTS['extensions'], **(config.get('extensions') or {})}
    return config


def save(config: dict[str, Any]) -> Path:
    """Write the configuration to disk and return its path."""
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + '\n')
    return CONFIG_PATH


def find_pyvista(configured: str | None = None) -> str | None:
    """Return the absolute path to the ``pyvista`` executable, or None if not found."""
    if configured:
        candidate = Path(configured).expanduser()
        return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None
    found = shutil.which('pyvista')
    if found:
        return found
    for directory in _CANDIDATE_DIRS:
        candidate = directory / 'pyvista'
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None
