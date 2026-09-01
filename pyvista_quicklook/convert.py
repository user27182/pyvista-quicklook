"""Turn mesh files into cached scenes the Quick Look extension can show interactively."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
from typing import Any

from . import config as config_mod
from .render import RenderError
from .render import _log
from .render import digest
from .render import identity_of

SCENE_VERSION = '2'
DEFAULT_MAX_POINTS = 2_000_000
EXPORTER = Path(__file__).with_name('_scene_export.py')


def max_points(config: dict[str, Any]) -> int:
    """Return the decimation cap, where zero means never decimate."""
    configured = config.get('max_scene_points')
    return DEFAULT_MAX_POINTS if configured is None else int(configured)


def scene_key(identity: tuple[str, int, int], config: dict[str, Any]) -> str:
    """Return the cache key for a file's interactive scene."""
    settings = [
        f'scene{SCENE_VERSION}',
        repr(config.get('max_scene_points')),
        repr(config.get('max_glyph_points')),
    ]
    return digest(identity, settings)


def scene(
    source: str | os.PathLike[str],
    config: dict[str, Any] | None = None,
    identity: tuple[str, int, int] | None = None,
) -> Path:
    """Return the path to a PLY scene for a mesh file, converting it if not cached."""
    config = config if config is not None else config_mod.load()
    path = Path(source).expanduser().resolve()

    if not path.is_file():
        message = f'No such file: {path}'
        raise RenderError(message)

    identity = identity or identity_of(path)
    interpreter = config_mod.find_python(config)
    if interpreter is None:
        message = (
            'The Python interpreter next to the pyvista executable was not found.\n'
            f'Set "pyvista" to its absolute path in {config_mod.CONFIG_PATH}.'
        )
        raise RenderError(message)

    out = config_mod.CACHE_DIR / f'{scene_key(identity, config)}.ply'
    if config.get('cache', True) and out.is_file() and out.stat().st_size:
        _log(config, f'hit  {path} (scene)')
        return out

    config_mod.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    scratch = out.with_suffix(f'.{os.getpid()}.tmp.ply')
    command = [
        interpreter,
        str(EXPORTER),
        str(path),
        str(scratch),
        '--max-points',
        str(max_points(config)),
        '--max-glyphs',
        str(config.get('max_glyph_points') or 20_000),
    ]
    environ = {**os.environ, 'PYVISTA_OFF_SCREEN': 'true', 'MPLBACKEND': 'Agg'}
    _log(config, f'miss {path} (scene)')

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
        message = f'Converting {path.name} timed out after {config.get("timeout")} s.'
        raise RenderError(message) from error

    if completed.returncode != 0 or not (scratch.is_file() and scratch.stat().st_size):
        scratch.unlink(missing_ok=True)
        detail = (completed.stderr or completed.stdout or '').strip()
        _log(config, f'fail {path} (scene)')
        message = f'Could not build an interactive scene for {path.name}.\n\n{detail}'
        raise RenderError(message)

    scratch.replace(out)
    _log(config, f'done {path} (scene) in {time.monotonic() - started:.1f}s')
    return out
