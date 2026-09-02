"""Turn mesh files into cached scenes the Quick Look extension can show interactively."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from . import cache
from . import config as config_mod
from . import environment

if TYPE_CHECKING:
    import os

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
    return cache.digest(identity, settings)


def scene(
    source: str | os.PathLike[str],
    config: dict[str, Any] | None = None,
    identity: tuple[str, int, int] | None = None,
) -> Path:
    """Return the path to a PLY scene for a mesh file, converting it if not cached."""
    config = config if config is not None else config_mod.load()
    path = environment.source_path(source)
    identity = identity or cache.identity_of(path)
    environment.check_size(identity, config)

    def build(scratch: Path) -> None:
        command = [
            environment.interpreter(config),
            str(EXPORTER),
            str(path),
            str(scratch),
            '--max-points',
            str(max_points(config)),
            '--max-glyphs',
            str(config.get('max_glyph_points') or 20_000),
        ]
        environment.run(config, command, task=f'Converting {path.name}', cwd=path.parent)

    out = config_mod.CACHE_DIR / f'{scene_key(identity, config)}.ply'
    return cache.fill(out, config, f'{path} (scene)', build)
