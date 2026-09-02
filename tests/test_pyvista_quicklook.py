"""Tests for the parts of pyvista_quicklook that do not render."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import plistlib
import sys
import threading
import time

import pytest

from pyvista_quicklook import cli
from pyvista_quicklook import config
from pyvista_quicklook import convert
from pyvista_quicklook import daemon
from pyvista_quicklook import environment
from pyvista_quicklook import formats
from pyvista_quicklook import plist
from pyvista_quicklook import render
from pyvista_quicklook import warmup


def test_normalize_accepts_any_spelling():
    """Extensions are lowercased and given exactly one leading dot."""
    assert formats.normalize('VTU') == '.vtu'
    assert formats.normalize('.VtU ') == '.vtu'


def test_default_extensions_are_claimed_and_known():
    """Every default extension appears in the format table."""
    defaults = formats.default_extensions()
    assert defaults
    assert set(defaults) <= set(formats.FORMATS)
    assert '.vtu' in defaults
    assert '.stl' not in defaults


def test_resolve_extensions_applies_config():
    """Additions and removals change the claimed set."""
    resolved = formats.resolve_extensions(add=['stl'], remove=['.vtu'])
    assert '.stl' in resolved
    assert '.vtu' not in resolved


def test_uti_is_unique_per_extension():
    """No two extensions share a uniform type identifier."""
    utis = [formats.uti_for(ext) for ext in formats.FORMATS]
    assert len(utis) == len(set(utis))


def test_app_plist_declares_every_extension():
    """The app exports one uniform type per claimed extension."""
    extensions = ['.vtu', '.vtp']
    declarations = plist.app_plist(extensions)['UTExportedTypeDeclarations']
    tags = [d['UTTypeTagSpecification']['public.filename-extension'] for d in declarations]
    assert tags == [['vtu'], ['vtp']]


def test_extension_plist_matches_the_app():
    """The extension supports exactly the types the app exports."""
    extensions = ['.vtu', '.vtp']
    app = plist.app_plist(extensions)
    ext = plist.extension_plist(extensions)
    exported = [d['UTTypeIdentifier'] for d in app['UTExportedTypeDeclarations']]
    supported = ext['NSExtension']['NSExtensionAttributes']['QLSupportedContentTypes']
    assert exported == supported
    assert ext['NSExtension']['NSExtensionPrincipalClass'] == plist.EXT_PRINCIPAL_CLASS
    assert ext['NSExtension']['NSExtensionPointIdentifier'] == 'com.apple.quicklook.preview'


def test_plists_are_writable(tmp_path):
    """Generated plists round-trip through plistlib."""
    target = tmp_path / 'Info.plist'
    plist.write(plist.app_plist(['.vtu']), target)
    assert plistlib.loads(target.read_bytes())['CFBundleIdentifier'] == plist.APP_BUNDLE_ID


def test_cache_key_follows_identity_not_the_rendered_file():
    """Two copies of one file share a preview when they carry the same identity."""
    config = {'window_size': [8, 8]}
    identity = ('/somewhere/mesh.vtu', 1234, 99)
    assert render.cache_key(identity, config) == render.cache_key(identity, config)
    assert render.cache_key(('/other.vtu', 1234, 99), config) != render.cache_key(identity, config)
    assert render.cache_key(('/somewhere/mesh.vtu', 1235, 99), config) != render.cache_key(
        identity, config
    )


def test_cache_key_follows_render_settings():
    """Changing the rendered size invalidates the preview."""
    identity = ('/mesh.vtu', 1, 2)
    assert render.cache_key(identity, {'window_size': [8, 8]}) != render.cache_key(
        identity, {'window_size': [9, 9]}
    )


def test_build_command_renders_off_screen():
    """The render command never opens a window."""
    command = render.build_command('/bin/pyvista', 'in.vtu', 'out.png', {'window_size': [64, 32]})
    assert command[:2] == ['/bin/pyvista', 'plot']
    assert '--off-screen' in command
    assert '--no-interactive' in command
    assert command[command.index('--window-size') + 1 : command.index('--window-size') + 3] == [
        '64',
        '32',
    ]


def test_build_command_passes_background_and_extra_args():
    """Optional settings reach the command line."""
    config = {'window_size': [1, 1], 'background': 'black', 'extra_args': ['--zoom', '2']}
    command = render.build_command('pyvista', 'in.vtu', 'out.png', config)
    assert '--background' in command
    assert command[-2:] == ['--zoom', '2']


def test_preview_rejects_files_above_the_limit(tmp_path):
    """A large file reports the limit instead of rendering."""
    sample = tmp_path / 'big.vtu'
    sample.write_bytes(b'x')
    config = {'max_file_size_mb': 1, 'window_size': [1, 1]}
    with pytest.raises(environment.RenderError, match='preview limit'):
        render.preview(sample, config, identity=(str(sample), 0, 5 * 1024 * 1024))


def test_preview_reports_a_missing_file(tmp_path):
    """A path that does not exist is reported plainly."""
    with pytest.raises(environment.RenderError, match='No such file'):
        render.preview(tmp_path / 'absent.vtu', {})


def test_write_json_is_atomic(tmp_path):
    """Replies appear complete or not at all."""
    target = tmp_path / 'reply.pvqlrep'
    daemon.write_json(target, {'ok': True})
    assert json.loads(target.read_text()) == {'ok': True}
    assert list(tmp_path.iterdir()) == [target]


def test_readable_rejects_a_missing_file(tmp_path):
    """The guard reports unreadable files without raising."""
    assert daemon.readable(str(tmp_path / 'nope')) is False


def test_readable_accepts_an_ordinary_file(tmp_path):
    """A file the service can open is reported readable."""
    sample = tmp_path / 'mesh.vtu'
    sample.write_text('data')
    assert daemon.readable(str(sample)) is True


def test_handle_reports_a_malformed_request(tmp_path):
    """A request that is not valid JSON produces an error reply."""
    request = tmp_path / 'token.pvqlreq'
    request.write_text('not json')
    daemon.handle(request)
    reply = json.loads((tmp_path / 'token.pvqlrep').read_text())
    assert reply['ok'] is False
    assert not request.exists()


def test_handle_falls_back_to_the_staged_copy(tmp_path, monkeypatch):
    """When the original cannot be read, the copy is rendered under the original's identity."""
    png = tmp_path / 'rendered.png'
    png.write_bytes(b'\x89PNG')
    seen = {}

    def fake_preview(source, config, identity=None):
        seen['source'] = str(source)
        seen['identity'] = identity
        return png

    monkeypatch.setattr(daemon.render_mod, 'preview', fake_preview)
    monkeypatch.setattr(daemon, 'folder_is_reachable', lambda path: False)

    request = tmp_path / 'token.pvqlreq'
    request.write_text(
        json.dumps(
            {
                'path': '/private/mesh.vtu',
                'copy': str(tmp_path / 'copy.vtu'),
                'mtime': 7,
                'size': 3,
            }
        )
    )
    daemon.handle(request)

    assert seen['source'] == str(tmp_path / 'copy.vtu')
    assert seen['identity'] == ('/private/mesh.vtu', 7, 3)
    reply = json.loads((tmp_path / 'token.pvqlrep').read_text())
    assert reply['ok'] is True
    assert (tmp_path / 'token.png').read_bytes() == b'\x89PNG'


def test_handle_reports_unreachable_files_without_a_copy(tmp_path, monkeypatch):
    """A request with no copy for an unreadable file explains the problem."""
    monkeypatch.setattr(daemon, 'folder_is_reachable', lambda path: False)
    request = tmp_path / 'token.pvqlreq'
    request.write_text(json.dumps({'path': '/private/mesh.vtu'}))
    daemon.handle(request)
    reply = json.loads((tmp_path / 'token.pvqlrep').read_text())
    assert reply['ok'] is False
    assert 'Privacy & Security' in reply['error']


def test_agent_plist_runs_the_daemon():
    """The launch agent starts the render service and keeps it running."""
    agent = daemon.agent_plist('/usr/local/bin/pvql')
    assert agent['ProgramArguments'] == ['/usr/local/bin/pvql', 'daemon']
    assert agent['KeepAlive'] is True
    assert agent['Label'] == daemon.LABEL


def test_parser_accepts_every_subcommand():
    """Each documented subcommand parses."""
    parser = cli.build_parser()
    for argv in (
        ['preview', 'mesh.vtu'],
        ['warm', 'dir'],
        ['types', '--all'],
        ['plist', '--app', 'a.plist', '--extension', 'e.plist'],
        ['config', '--init'],
        ['cache', '--clear'],
        ['doctor'],
        ['daemon'],
        ['service', '--install'],
    ):
        assert parser.parse_args(argv).func is not None


def test_claimed_extensions_follows_config():
    """The claimed set reflects the config additions and removals."""
    claimed = cli.claimed_extensions({'extensions': {'add': ['.stl'], 'remove': ['.vtu']}})
    assert '.stl' in claimed
    assert '.vtu' not in claimed


def test_types_lists_claimed_extensions(capsys, monkeypatch):
    """`pvql types` prints one line per claimed extension."""
    monkeypatch.setattr(cli.config_mod, 'load', lambda: dict(cli.config_mod.DEFAULTS))
    assert cli.cmd_types(argparse.Namespace(all=False)) == 0
    out = capsys.readouterr().out
    assert '.vtu' in out
    assert 'extensions claimed' in out


def test_plist_writes_both_files(tmp_path, monkeypatch):
    """`pvql plist` writes an app and an extension property list."""
    monkeypatch.setattr(cli.config_mod, 'load', lambda: dict(cli.config_mod.DEFAULTS))
    app = tmp_path / 'App.plist'
    ext = tmp_path / 'Ext.plist'
    args = argparse.Namespace(app=str(app), extension=str(ext), helper='/bin/pvql')
    assert cli.cmd_plist(args) == 0
    assert plistlib.loads(app.read_bytes())['PVQLHelperPath'] == '/bin/pvql'
    assert plistlib.loads(ext.read_bytes())['CFBundlePackageType'] == 'XPC!'


def test_preview_reports_failures_on_stderr(capsys, monkeypatch):
    """A render failure exits non-zero and explains itself."""

    def fail(path, config):
        message = 'nope'
        raise environment.RenderError(message)

    monkeypatch.setattr(cli.config_mod, 'load', lambda: dict(cli.config_mod.DEFAULTS))
    monkeypatch.setattr(cli.render_mod, 'preview', fail)
    args = argparse.Namespace(path='mesh.vtu', output=None, no_cache=True)
    assert cli.cmd_preview(args) == 1
    assert 'nope' in capsys.readouterr().err


def test_preview_prints_the_cached_path(capsys, monkeypatch, tmp_path):
    """A successful render prints where the preview landed."""
    png = tmp_path / 'out.png'
    png.write_bytes(b'x')
    monkeypatch.setattr(cli.config_mod, 'load', lambda: dict(cli.config_mod.DEFAULTS))
    monkeypatch.setattr(cli.render_mod, 'preview', lambda path, config: png)
    args = argparse.Namespace(path='mesh.vtu', output=None, no_cache=False)
    assert cli.cmd_preview(args) == 0
    assert str(png) in capsys.readouterr().out


def test_cache_reports_its_size(capsys, monkeypatch, tmp_path):
    """`pvql cache` reports the cache location and contents."""
    (tmp_path / 'a.png').write_bytes(b'0123456789')
    monkeypatch.setattr(cli.config_mod, 'CACHE_DIR', tmp_path)
    assert cli.cmd_cache(argparse.Namespace(clear=False)) == 0
    assert '1 previews' in capsys.readouterr().out


def test_config_load_merges_over_defaults(tmp_path, monkeypatch):
    """Unknown keys are dropped and missing ones fall back to defaults."""
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'timeout': 5, 'bogus': 1}))
    monkeypatch.setattr(config.CONFIG_PATH, '__class__', type(path), raising=False)
    monkeypatch.setattr(config, 'CONFIG_PATH', path)
    loaded = config.load()
    assert loaded['timeout'] == 5
    assert 'bogus' not in loaded
    assert loaded['window_size'] == config.DEFAULTS['window_size']


def test_config_load_survives_broken_json(tmp_path, monkeypatch):
    """A corrupt config file falls back to defaults instead of raising."""
    path = tmp_path / 'config.json'
    path.write_text('{not json')
    monkeypatch.setattr(config, 'CONFIG_PATH', path)
    assert config.load()['timeout'] == config.DEFAULTS['timeout']


def test_find_pyvista_rejects_a_missing_executable(tmp_path):
    """A configured path that is not executable is reported as not found."""
    assert config.find_pyvista(str(tmp_path / 'absent')) is None


def test_find_pyvista_accepts_a_configured_executable(tmp_path):
    """A configured executable is used as given."""
    tool = tmp_path / 'pyvista'
    tool.write_text('#!/bin/sh\n')
    tool.chmod(0o755)
    assert config.find_pyvista(str(tool)) == str(tool)


def test_bundle_version_is_numeric():
    """Bundle versions carry only the leading numeric part."""
    assert plist.bundle_version('1.2.3.dev4+gabc') == '1.2.3'
    assert plist.bundle_version('nonsense') == '0.0.0'


def test_scene_key_differs_from_the_image_key():
    """A file's scene and its rendered image are cached separately."""
    identity = ('/mesh.vtu', 1, 2)
    settings = {'window_size': [8, 8], 'max_scene_points': 100, 'max_glyph_points': 20}
    assert convert.scene_key(identity, settings) != render.cache_key(identity, settings)


def test_scene_key_follows_conversion_settings():
    """Changing either point budget invalidates the scene."""
    identity = ('/mesh.vtu', 1, 2)
    base = {'max_scene_points': 100, 'max_glyph_points': 20}
    assert convert.scene_key(identity, base) != convert.scene_key(
        identity, {**base, 'max_scene_points': 200}
    )
    assert convert.scene_key(identity, base) != convert.scene_key(
        identity, {**base, 'max_glyph_points': 40}
    )


def test_scene_passes_a_zero_glyph_budget_through(tmp_path, monkeypatch):
    """A glyph budget of zero means no cap, and must not fall back to the default."""
    sample = tmp_path / 'mesh.vtu'
    sample.write_text('x')
    seen = {}

    def fake_run(config, command, **kwargs):
        seen['command'] = command
        Path(command[3]).write_bytes(b'ply')

    monkeypatch.setattr(convert.environment, 'run', fake_run)
    monkeypatch.setattr(convert.config_mod, 'CACHE_DIR', tmp_path / 'cache')
    config = {'python': sys.executable, 'max_glyph_points': 0, 'cache': False}
    out = convert.scene(sample, config)
    command = seen['command']
    assert command[command.index('--max-glyphs') + 1] == '0'
    assert command[command.index('--max-points') + 1] == str(config_defaults()['max_scene_points'])
    assert out.read_bytes() == b'ply'


def config_defaults():
    """Return a copy of the built-in configuration."""
    return dict(config.DEFAULTS)


def test_scene_reports_a_missing_file(tmp_path):
    """Converting a file that is not there is reported plainly."""
    with pytest.raises(environment.RenderError, match='No such file'):
        convert.scene(tmp_path / 'absent.vtu', {})


def test_scene_rejects_files_above_the_limit(tmp_path):
    """The interactive path honours the size limit before it looks for PyVista."""
    sample = tmp_path / 'big.vtu'
    sample.write_bytes(b'x')
    config = {'max_file_size_mb': 1, 'python': str(tmp_path / 'absent')}
    with pytest.raises(environment.RenderError, match='preview limit'):
        convert.scene(sample, config, identity=(str(sample), 0, 5 * 1024 * 1024))


def test_build_scene_is_skipped_when_not_interactive():
    """Turning interactivity off falls straight through to the rendered image."""
    assert daemon.build_scene('/mesh.vtu', {'interactive': False}, None) == (None, None)


def test_build_scene_falls_back_when_conversion_fails(monkeypatch):
    """A dataset that cannot be converted falls back to the rendered image."""

    def fail(target, config, identity=None):
        message = 'no surface'
        raise environment.RenderError(message)

    monkeypatch.setattr(daemon.convert_mod, 'scene', fail)
    built, why = daemon.build_scene('/mesh.vtu', {'interactive': True}, None)
    assert built is None
    assert 'no surface' in why


def test_handle_delivers_an_interactive_scene(tmp_path, monkeypatch):
    """When a scene is built, the reply points at it rather than an image."""
    ply = tmp_path / 'scene.ply'
    ply.write_bytes(b'ply\n')
    monkeypatch.setattr(daemon, 'folder_is_reachable', lambda path: True)
    monkeypatch.setattr(daemon.convert_mod, 'scene', lambda target, config, identity=None: ply)

    request = tmp_path / 'token.pvqlreq'
    request.write_text(json.dumps({'path': str(tmp_path / 'mesh.vtu'), 'mtime': 1, 'size': 2}))
    daemon.handle(request)

    reply = json.loads((tmp_path / 'token.pvqlrep').read_text())
    assert reply['ok'] is True
    assert reply['scene'].endswith('token.ply')
    assert (tmp_path / 'token.ply').read_bytes() == b'ply\n'


def test_find_python_prefers_the_configured_interpreter(tmp_path):
    """An explicit interpreter is used as given."""
    tool = tmp_path / 'python'
    tool.write_text('#!/bin/sh\n')
    tool.chmod(0o755)
    assert config.find_python({'python': str(tool)}) == str(tool)


def test_find_python_falls_back_to_the_pyvista_sibling(tmp_path):
    """A configuration naming only the CLI still yields its interpreter."""
    for name in ('pyvista', 'python3'):
        tool = tmp_path / name
        tool.write_text('#!/bin/sh\n')
        tool.chmod(0o755)
    assert config.find_python({'pyvista': str(tmp_path / 'pyvista')}) == str(tmp_path / 'python3')


def test_find_python_reports_nothing_without_an_environment(monkeypatch):
    """No interpreter and no CLI means no environment."""
    monkeypatch.setattr(config, 'find_pyvista', lambda configured=None: None)
    assert config.find_python({}) is None


def test_warmup_script_ships_with_the_package():
    """The warm-up script the PyVista interpreter runs is part of the package."""
    assert warmup.WARMER.is_file()


def test_warm_reports_a_missing_interpreter(monkeypatch):
    """Warming without a usable PyVista environment explains what to set."""
    monkeypatch.setattr(warmup.config_mod, 'find_python', lambda configured=None: None)
    with pytest.raises(environment.RenderError, match='interpreter'):
        warmup.warm({})


def test_warm_in_background_does_not_raise(monkeypatch):
    """A failing warm-up never brings the service down."""
    started = threading.Event()

    def explode(config):
        started.set()
        message = 'no interpreter'
        raise environment.RenderError(message)

    monkeypatch.setattr(daemon.warmup_mod, 'warmed_recently', lambda: False)
    monkeypatch.setattr(daemon.warmup_mod, 'warm', explode)
    daemon.warm_in_background({})
    assert started.wait(timeout=5)


def test_warmed_recently_reads_the_stamp(tmp_path, monkeypatch):
    """A fresh stamp counts as warm; a missing one does not."""
    monkeypatch.setattr(warmup.config_mod, 'CACHE_DIR', tmp_path)
    assert warmup.warmed_recently() is False
    warmup.stamp_path().touch()
    assert warmup.warmed_recently() is True
    assert warmup.warmed_recently(within=0) is False


def test_warm_in_background_skips_a_recent_warm_up(monkeypatch):
    """The service does not compete with a warm-up the installer just ran."""
    called = []
    monkeypatch.setattr(daemon.warmup_mod, 'warmed_recently', lambda: True)
    monkeypatch.setattr(daemon.warmup_mod, 'warm', lambda config: called.append(config))
    daemon.warm_in_background({})
    time.sleep(0.2)
    assert called == []


def test_overrides_drops_settings_that_match_the_defaults():
    """Only deliberate changes are stored, so defaults stay free to improve."""
    merged = {**config.DEFAULTS, 'pyvista': '/bin/pyvista', 'timeout': 5}
    stored = config.overrides(merged)
    assert stored == {'pyvista': '/bin/pyvista', 'timeout': 5}
    assert 'max_scene_points' not in stored


def test_overrides_round_trips_through_load(tmp_path, monkeypatch):
    """A stored override survives, and everything else follows the defaults."""
    path = tmp_path / 'config.json'
    monkeypatch.setattr(config, 'CONFIG_PATH', path)
    path.write_text(json.dumps(config.overrides({**config.DEFAULTS, 'timeout': 5})))
    loaded = config.load()
    assert loaded['timeout'] == 5
    assert loaded['max_scene_points'] == config.DEFAULTS['max_scene_points']


def test_handle_reports_why_the_scene_failed(tmp_path, monkeypatch):
    """Without a still-image fallback the scene's own error is what gets reported."""

    def no_scene(target, config, identity=None):
        message = 'the dataset has no surface to show'
        raise environment.RenderError(message)

    def no_renderer(target, config, identity=None):
        message = 'The pyvista command-line interface was not found.'
        raise environment.RenderError(message)

    monkeypatch.setattr(daemon, 'folder_is_reachable', lambda path: True)
    monkeypatch.setattr(daemon.convert_mod, 'scene', no_scene)
    monkeypatch.setattr(daemon.render_mod, 'preview', no_renderer)

    request = tmp_path / 'token.pvqlreq'
    request.write_text(json.dumps({'path': str(tmp_path / 'mesh.vtu'), 'mtime': 1, 'size': 2}))
    daemon.handle(request)

    reply = json.loads((tmp_path / 'token.pvqlrep').read_text())
    assert reply['ok'] is False
    assert 'no surface' in reply['error']
    assert 'command-line interface' not in reply['error']


def test_config_init_with_an_interpreter_clears_a_stale_cli(tmp_path, monkeypatch):
    """An environment named by interpreter does not keep an unrelated CLI on record."""
    path = tmp_path / 'config.json'
    monkeypatch.setattr(config, 'CONFIG_PATH', path)
    monkeypatch.setattr(config, 'APP_SUPPORT', tmp_path)
    path.write_text(json.dumps({'pyvista': '/old/bin/pyvista'}))
    args = argparse.Namespace(
        init=True, python='/new/bin/python', pyvista=None, helper='/bin/pvql'
    )
    cli.cmd_config(args)
    stored = json.loads(path.read_text())
    assert stored['python'] == '/new/bin/python'
    assert 'pyvista' not in stored


def test_resolve_pyvista_stays_inside_the_configured_environment(tmp_path):
    """A configured interpreter without a sibling CLI does not fall back to PATH."""
    interpreter = tmp_path / 'python'
    interpreter.write_text('#!/bin/sh\n')
    interpreter.chmod(0o755)
    assert config.resolve_pyvista({'python': str(interpreter)}) is None

    sibling = tmp_path / 'pyvista'
    sibling.write_text('#!/bin/sh\n')
    sibling.chmod(0o755)
    assert config.resolve_pyvista({'python': str(interpreter)}) == str(sibling)
