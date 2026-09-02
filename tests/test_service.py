"""End-to-end tests that run the exporter and warm-up under a real PyVista interpreter."""

from __future__ import annotations

import json
import sys

import pytest
import pyvista as pv

from pyvista_quicklook import config
from pyvista_quicklook import convert
from pyvista_quicklook import daemon
from pyvista_quicklook import environment
from pyvista_quicklook import render
from pyvista_quicklook import warmup


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Return a configuration naming the test interpreter, with a cache of its own."""
    monkeypatch.setattr(config, 'CACHE_DIR', tmp_path / 'cache')
    return {**config.DEFAULTS, 'python': sys.executable}


def test_scene_is_built_by_the_exporter_and_cached(tmp_path, env, monkeypatch):
    """The exporter runs under the configured interpreter and its output is kept."""
    source = tmp_path / 'sphere.vtp'
    pv.Sphere().save(source)
    out = convert.scene(source, env)
    assert out.parent == config.CACHE_DIR
    assert out.name.startswith(f'{convert.SCENE_VERSION}-')
    assert pv.read(out).n_faces > 0
    assert not list(config.CACHE_DIR.glob('*.tmp*'))

    def never(*args, **kwargs):
        pytest.fail('a cached scene must not be built again')

    monkeypatch.setattr(convert.environment, 'run', never)
    assert convert.scene(source, env) == out


def test_scene_reports_what_the_exporter_said(tmp_path, env):
    """A file the exporter cannot handle is reported, and nothing is left in the cache."""
    source = tmp_path / 'broken.vtp'
    source.write_text('not a mesh')
    with pytest.raises(environment.RenderError, match=r'Converting broken\.vtp failed'):
        convert.scene(source, env)
    assert not list(config.CACHE_DIR.glob('*'))


def test_handle_answers_with_a_scene_for_a_real_file(tmp_path, env, monkeypatch):
    """A request for a readable file is answered with a scene the extension can load."""
    monkeypatch.setattr(daemon.config_mod, 'load', lambda: env)
    source = tmp_path / 'sphere.vtp'
    pv.Sphere().save(source)
    request = tmp_path / 'token.pvqlreq'
    request.write_text(json.dumps({'path': str(source), 'mtime': 1, 'size': 2}))
    daemon.handle(request)
    reply = json.loads((tmp_path / 'token.pvqlrep').read_text())
    assert reply['ok'] is True
    assert pv.read(reply['scene']).n_points > 0


def test_warm_runs_the_warmer_and_leaves_a_stamp(env):
    """Warming loads PyVista in the configured interpreter and records when it finished."""
    assert not warmup.warmed_recently()
    assert warmup.warm(env) > 0
    assert warmup.warmed_recently()


@pytest.mark.needs_rendering
@pytest.mark.skipif(sys.platform != 'darwin', reason='rendering needs a display server on Linux')
def test_still_images_come_from_the_pyvista_command(tmp_path, env):
    """The environment can render a still image, which is what non-interactive mode shows."""
    source = tmp_path / 'sphere.vtp'
    pv.Sphere().save(source)
    png = render.preview(source, env)
    assert png.suffix == '.png'
    assert png.stat().st_size > 0
    assert daemon.produce(source, {**env, 'interactive': False}) == png
