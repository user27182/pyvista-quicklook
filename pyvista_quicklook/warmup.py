"""Import PyVista and VTK ahead of time so the first preview does not pay for them."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
from typing import Any

from . import config as config_mod
from .render import RenderError
from .render import _log

WARMER = Path(__file__).with_name('_warmup.py')
TIMEOUT = 300
RECENT_SECONDS = 120


def stamp_path() -> Path:
    """Return the file whose modification time records the last warm-up."""
    return config_mod.CACHE_DIR / '.warm'


def warmed_recently(within: float = RECENT_SECONDS) -> bool:
    """Return whether a warm-up finished within the given number of seconds."""
    try:
        return time.time() - stamp_path().stat().st_mtime < within
    except OSError:
        return False


def warm(config: dict[str, Any] | None = None) -> float:
    """Load PyVista and VTK in the configured environment and return how long it took."""
    config = config if config is not None else config_mod.load()
    interpreter = config_mod.find_python(config.get('pyvista'))
    if interpreter is None:
        message = (
            'The Python interpreter next to the pyvista executable was not found.\n'
            f'Set "pyvista" to its absolute path in {config_mod.CONFIG_PATH}.'
        )
        raise RenderError(message)

    environ = {**os.environ, 'PYVISTA_OFF_SCREEN': 'true', 'MPLBACKEND': 'Agg'}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [interpreter, str(WARMER)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=environ,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        message = f'Warming PyVista timed out after {TIMEOUT} s.'
        raise RenderError(message) from error

    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or '').strip()
        message = f'Could not warm PyVista.\n\n{detail}'
        raise RenderError(message)

    try:
        config_mod.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        stamp_path().touch()
    except OSError:
        pass

    _log(config, f'warm in {elapsed:.1f}s')
    return elapsed
