"""The source installer's handling of uv, run against stand-in uv and pvql commands."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tomllib

import pytest

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
