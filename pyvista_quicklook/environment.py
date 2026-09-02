"""Run work in the PyVista environment named by the configuration."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
from typing import Any

from . import config as config_mod

# A service must never open a window, and matplotlib must never look for one.
ENVIRON = {'PYVISTA_OFF_SCREEN': 'true', 'MPLBACKEND': 'Agg'}


class RenderError(Exception):
    """Raised when a preview cannot be produced."""


def log(config: dict[str, Any], message: str) -> None:
    """Append a timestamped message to the log file when logging is enabled."""
    if not config.get('log'):
        return
    try:
        config_mod.APP_SUPPORT.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with config_mod.LOG_PATH.open('a') as handle:
            handle.write(f'{stamp} {message}\n')
    except OSError:
        pass


def source_path(source: str | os.PathLike[str]) -> Path:
    """Return the resolved path of a file to preview, which must exist."""
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        message = f'No such file: {path}'
        raise RenderError(message)
    return path


def interpreter(config: dict[str, Any]) -> str:
    """Return the configured interpreter, or say what to set when there is none."""
    found = config_mod.find_python(config)
    if found is None:
        message = (
            'No PyVista environment is configured.\n'
            f'Set "python" to its interpreter in {config_mod.CONFIG_PATH}.'
        )
        raise RenderError(message)
    return found


def run(
    config: dict[str, Any],
    command: list[str],
    *,
    task: str,
    cwd: Path | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command in the PyVista environment, raising ``RenderError`` if it fails.

    ``task`` names the work for error messages, as in ``Rendering mesh.vtu``.
    """
    if timeout is None:
        timeout = config.get('timeout') or config_mod.DEFAULTS['timeout']
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **ENVIRON},
            cwd=None if cwd is None else str(cwd),
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        message = f'{task} timed out after {timeout:g} s.'
        raise RenderError(message) from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or '').strip()
        message = f'{task} failed.\n\n{tail(detail)}'
        raise RenderError(message)
    return completed


def tail(text: str, limit: int = 40) -> str:
    """Return the last non-blank lines of a command's output."""
    lines = [line for line in text.splitlines() if line.strip()]
    return '\n'.join(lines[-limit:])
