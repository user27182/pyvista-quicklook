"""Render mesh files to cached PNG previews with the ``pyvista`` command-line interface."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from . import config as config_mod

CACHE_VERSION = '1'


class RenderError(Exception):
    """Raised when a preview cannot be produced."""


def _log(config: dict[str, Any], message: str) -> None:
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


def identity_of(path: Path) -> tuple[str, int, int]:
    """Return the path, whole-second modification time, and size that identify a file."""
    stat = path.stat()
    return str(path), int(stat.st_mtime), stat.st_size


def digest(identity: tuple[str, int, int], settings: list[str]) -> str:
    """Return a cache key for a file rendered with the given settings."""
    source, mtime, size = identity
    parts = [CACHE_VERSION, source, str(mtime), str(size), *settings]
    return hashlib.sha256('\0'.join(parts).encode()).hexdigest()


def cache_key(identity: tuple[str, int, int], config: dict[str, Any]) -> str:
    """Return the cache key for a file under the current render settings."""
    settings = [
        repr(config.get('window_size')),
        repr(config.get('background')),
        repr(config.get('extra_args')),
    ]
    return digest(identity, settings)


def build_command(executable: str, path: Path, out: Path, config: dict[str, Any]) -> list[str]:
    """Return the ``pyvista plot`` command used to render a preview."""
    width, height = config.get('window_size') or [1024, 1024]
    command = [
        executable,
        'plot',
        str(path),
        '--off-screen',
        '--no-interactive',
        '--screenshot',
        str(out),
        '--window-size',
        str(int(width)),
        str(int(height)),
    ]
    if config.get('background'):
        command += ['--background', str(config['background'])]
    command += [str(arg) for arg in config.get('extra_args') or []]
    return command


def preview(
    source: str | os.PathLike[str],
    config: dict[str, Any] | None = None,
    identity: tuple[str, int, int] | None = None,
) -> Path:
    """Return the path to a PNG preview of a mesh file, rendering it if not cached.

    ``identity`` names the file the preview belongs to when ``source`` is a copy of it.
    """
    config = config if config is not None else config_mod.load()
    path = Path(source).expanduser().resolve()

    if not path.is_file():
        message = f'No such file: {path}'
        raise RenderError(message)

    identity = identity or identity_of(path)
    limit_mb = config.get('max_file_size_mb') or 0
    size_mb = identity[2] / 1024 / 1024
    if limit_mb and size_mb > limit_mb:
        name = Path(identity[0]).name
        message = (
            f'{name} is {size_mb:.0f} MB, above the {limit_mb} MB preview limit.\n'
            f'Raise "max_file_size_mb" in {config_mod.CONFIG_PATH} to preview it.'
        )
        raise RenderError(message)

    executable = config_mod.resolve_pyvista(config)
    if executable is None:
        message = (
            'The pyvista command-line interface was not found.\n'
            f'Set "pyvista" to its absolute path in {config_mod.CONFIG_PATH}.'
        )
        raise RenderError(message)

    out = config_mod.CACHE_DIR / f'{cache_key(identity, config)}.png'
    if config.get('cache', True) and out.is_file() and out.stat().st_size:
        _log(config, f'hit  {path}')
        return out

    config_mod.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    scratch = out.with_suffix(f'.{os.getpid()}.tmp.png')
    command = build_command(executable, path, scratch, config)
    environ = {**os.environ, 'PYVISTA_OFF_SCREEN': 'true', 'MPLBACKEND': 'Agg'}
    _log(config, f'miss {path}')

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=config.get('timeout') or 60,
            env=environ,
            cwd=str(path.parent),
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        scratch.unlink(missing_ok=True)
        message = f'Rendering {path.name} timed out after {config.get("timeout")} s.'
        raise RenderError(message) from error
    elapsed = time.monotonic() - started

    if completed.returncode != 0 or not (scratch.is_file() and scratch.stat().st_size):
        scratch.unlink(missing_ok=True)
        detail = (completed.stderr or completed.stdout or '').strip()
        _log(config, f'fail {path}: {detail.splitlines()[-1] if detail else "no output"}')
        message = f'pyvista could not plot {path.name}.\n\n{_tail(detail)}'
        raise RenderError(message)

    scratch.replace(out)
    _log(config, f'done {path} in {elapsed:.1f}s')
    return out


def _tail(text: str, limit: int = 40) -> str:
    """Return the last lines of a command's output."""
    lines = [line for line in text.splitlines() if line.strip()]
    return '\n'.join(lines[-limit:])


CACHED_SUFFIXES = ('*.png', '*.ply')


def cached_previews() -> list[Path]:
    """Return every cached preview, both rendered images and interactive scenes."""
    if not config_mod.CACHE_DIR.is_dir():
        return []
    return [e for pattern in CACHED_SUFFIXES for e in config_mod.CACHE_DIR.glob(pattern)]


def clear_cache() -> int:
    """Delete every cached preview and return the number of files removed."""
    removed = 0
    for entry in cached_previews():
        entry.unlink(missing_ok=True)
        removed += 1
    return removed
