"""Turn mesh files into cached scenes the Quick Look extension can show interactively."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from . import cache
from . import config as config_mod
from . import environment

if TYPE_CHECKING:
    import os

EXPORTER = Path(__file__).with_name('_scene_export.py')


def exporter_version(exporter: Path = EXPORTER) -> str:
    """Return a short digest of the exporter, which changes whenever its output might."""
    return hashlib.sha256(exporter.read_bytes()).hexdigest()[:12]


# Scenes carry this in their key and their name, so an update never serves an old one.
SCENE_VERSION = exporter_version()


def budget(config: dict[str, Any], key: str) -> int:
    """Return a point budget from the configuration, where zero means no limit."""
    configured = config.get(key)
    return int(config_mod.DEFAULTS[key] if configured is None else configured)


def scene_key(identity: tuple[str, int, int], config: dict[str, Any]) -> str:
    """Return the cache key for a file's interactive scene."""
    settings = [
        SCENE_VERSION,
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
            str(budget(config, 'max_scene_points')),
            '--max-glyphs',
            str(budget(config, 'max_glyph_points')),
        ]
        environment.run(config, command, task=f'Converting {path.name}', cwd=path.parent)

    out = config_mod.CACHE_DIR / f'{SCENE_VERSION}-{scene_key(identity, config)}.ply'
    return cache.fill(out, config, f'{path} (scene)', build)
