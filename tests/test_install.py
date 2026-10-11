"""The source installer's handling of uv, run against stand-in uv and pvql commands."""

from __future__ import annotations

from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tomllib

import pytest

from pyvista_quicklook import plist as plist_mod

ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / 'scripts' / 'install-from-source.sh'
SCRIPT = INSTALLER.read_text()
UV_MIN = re.search(r'^UV_MIN="([\d.]+)"$', SCRIPT, re.MULTILINE).group(1)
PYTHON_VERSION = re.search(
    r'^PYTHON_VERSION="\$\{PVQL_PYTHON:-([\d.]+)\}"$', SCRIPT, re.MULTILINE
).group(1)
REACHED_CONFIGURATION = '==> recording configuration'

STAND_IN_UV = Path(__file__).parent / 'data' / 'stand-in-uv.sh'


def run_installer(tmp_path, version, update_to=''):
    """Run the installer with a uv reporting ``version``; return the result and uv's calls."""
    assert SCRIPT.index('config --init') < SCRIPT.index('lsregister'), (
        'the stand-in pvql must stop the installer before it registers anything'
    )
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    uv = bin_dir / 'uv'
    uv.write_bytes(STAND_IN_UV.read_bytes())
    pvql = bin_dir / 'pvql'
    pvql.write_text('#!/bin/sh\nexit 1\n')
    for tool in (uv, pvql):
        tool.chmod(0o755)
    (tmp_path / 'uv-version').write_text(version)
    log = tmp_path / 'uv.log'
    log.touch()
    env = {
        'HOME': str(tmp_path / 'home'),
        'PATH': f'{bin_dir}:/usr/bin:/bin',
        'STAND_IN_LOG': str(log),
        'STAND_IN_VERSION': str(tmp_path / 'uv-version'),
        'STAND_IN_UPDATE_TO': update_to,
        'STAND_IN_EXCLUDES': str(tmp_path / 'excludes'),
    }
    result = subprocess.run(
        [str(INSTALLER), '--app', str(tmp_path / 'App.app'), '--skip-helper'],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result, log.read_text()


def test_installer_resolves_without_stock_vtk(tmp_path):
    """The PyVista environment is installed with vtk excluded from the resolve."""
    result, log = run_installer(tmp_path, '0.11.14')
    assert REACHED_CONFIGURATION in result.stdout, result.stderr
    assert any(line.startswith('pip install') for line in log.splitlines())
    assert (tmp_path / 'excludes').read_text().split() == ['vtk']


@pytest.mark.parametrize('version', ['0.10', '0.10.0', '0.10.1', '0.11.14', '1.0.0'])
def test_installer_keeps_a_new_enough_uv(tmp_path, version):
    """A uv at or above the floor is used as it is."""
    result, log = run_installer(tmp_path, version)
    assert REACHED_CONFIGURATION in result.stdout, result.stderr
    assert 'self update' not in log


@pytest.mark.parametrize('version', ['0.2.0', '0.9.7', '0.9.20'])
def test_installer_updates_an_old_uv(tmp_path, version):
    """A uv below the floor is updated, and the install goes on."""
    result, log = run_installer(tmp_path, version, update_to='0.13.0')
    assert f'==> updating uv {version}, which is older than {UV_MIN}' in result.stdout
    assert 'self update' in log
    assert REACHED_CONFIGURATION in result.stdout, result.stderr


@pytest.mark.parametrize(('version', 'shown'), [('0.9.7', '0.9.7'), ('', 'unknown')])
def test_installer_stops_on_a_uv_that_cannot_update(tmp_path, version, shown):
    """A uv that stays below the floor stops the install before anything is created."""
    result, log = run_installer(tmp_path, version)
    assert result.returncode == 1
    assert 'error: cannot self-update this uv' in result.stderr
    uv = tmp_path / 'bin' / 'uv'
    assert f'uv {shown} at {uv} is older than {UV_MIN}' in result.stderr
    assert 'venv' not in log
    assert not (tmp_path / 'home').exists()


def test_project_requires_the_installer_uv():
    """pyproject.toml asks for the same uv as the installer."""
    tool_uv = tomllib.loads((ROOT / 'pyproject.toml').read_text())['tool']['uv']
    assert tool_uv['required-version'] == f'>={UV_MIN}'


def test_lockfile_excludes_stock_vtk():
    """The committed lock records the exclusion and holds no vtk."""
    lock = tomllib.loads((ROOT / 'uv.lock').read_text())
    assert lock['manifest']['excludes'] == ['vtk']
    assert 'vtk' not in {package['name'] for package in lock['package']}


def test_readme_names_the_installer_python():
    """Every Python the README names is the one the installer and project use."""
    readme = (ROOT / 'README.md').read_text()
    assert set(re.findall(r'Python,? (3\.\d+)', readme)) == {PYTHON_VERSION}
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    assert project['requires-python'].split(',')[0] == f'>={PYTHON_VERSION}'


def script_lines(first, last):
    """Return the installer's lines from the one starting ``first`` through ``last``."""
    start = SCRIPT.index(first)
    return SCRIPT[start : SCRIPT.index(last, start) + len(last)]


def ask_to_restart_finder(tmp_path, answer):
    """Run the Finder prompt with ``answer`` typed; return its output and killall's calls."""
    calls = tmp_path / 'killall.log'
    killall = tmp_path / 'killall'
    killall.write_text(f'#!/bin/sh\necho "$@" >> {calls}\n')
    killall.chmod(0o755)
    function = script_lines('restart_finder() {', '\n}\n').replace(
        '/usr/bin/killall', str(killall)
    )
    script = f'{function}restart_finder 3<<< {answer!r}\n'
    result = subprocess.run(
        ['/bin/bash', '-c', script], capture_output=True, text=True, timeout=10, check=True
    )
    return result.stdout, calls.read_text() if calls.exists() else ''


@pytest.mark.parametrize('answer', ['y', 'Y', 'yes'])
def test_finder_is_restarted_on_yes(tmp_path, answer):
    """A yes restarts the Finder, after the risk is explained."""
    output, calls = ask_to_restart_finder(tmp_path, answer)
    assert 'Make sure no files are currently being moved or copied.' in output
    assert calls == 'Finder\n'


@pytest.mark.parametrize('answer', ['n', '', 'sure'])
def test_finder_is_left_running_otherwise(tmp_path, answer):
    """Anything but a yes leaves the Finder alone and says how to finish later."""
    output, calls = ask_to_restart_finder(tmp_path, answer)
    assert calls == ''
    assert 'Restart it later with "killall Finder"' in output


@pytest.mark.skipif(sys.platform != 'darwin', reason='PlistBuddy is macOS only')
@pytest.mark.parametrize(
    ('identifier', 'stale'),
    [(plist_mod.LEGACY_APP_BUNDLE_ID, '1'), (plist_mod.APP_BUNDLE_ID, '0'), (None, '0')],
)
def test_an_install_under_the_old_identifier_is_detected(tmp_path, identifier, stale):
    """Only an app installed under the identifier from before 0.7.0 marks the Finder stale."""
    app = tmp_path / 'PyVista Quick Look.app'
    if identifier:
        (app / 'Contents').mkdir(parents=True)
        info = plistlib.dumps({'CFBundleIdentifier': identifier})
        (app / 'Contents' / 'Info.plist').write_bytes(info)
    legacy = script_lines('LEGACY_BUNDLE_ID=', '\n')
    detection = script_lines('STALE_FINDER=0', '\ndone\n')
    script = (
        f'{legacy}APP={str(app)!r}\nLEGACY_APP=/nonexistent\n{detection}echo "$STALE_FINDER"\n'
    )
    result = subprocess.run(
        ['/bin/bash', '-c', script], capture_output=True, text=True, timeout=10, check=True
    )
    assert result.stdout.strip() == stale
