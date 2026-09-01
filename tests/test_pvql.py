"""Tests for the parts of pvql that do not render."""

from __future__ import annotations

import json
import plistlib

import pytest

from pvql import daemon
from pvql import formats
from pvql import plist
from pvql import render


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
    with pytest.raises(render.RenderError, match='preview limit'):
        render.preview(sample, config, identity=(str(sample), 0, 5 * 1024 * 1024))


def test_preview_reports_a_missing_file(tmp_path):
    """A path that does not exist is reported plainly."""
    with pytest.raises(render.RenderError, match='No such file'):
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
        json.dumps({'path': '/private/mesh.vtu', 'copy': str(tmp_path / 'copy.vtu'), 'mtime': 7, 'size': 3})
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
