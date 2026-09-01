"""Command-line interface for the PyVista Quick Look helper."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time

from . import config as config_mod
from . import daemon as daemon_mod
from . import plist as plist_mod
from . import render as render_mod
from .formats import FORMATS
from .formats import resolve_extensions
from .formats import uti_for

# A tetrahedron in legacy VTK format, used by ``pvql doctor`` as a smoke test.
SMOKE_MESH = """# vtk DataFile Version 3.0
pvql doctor
ASCII
DATASET POLYDATA
POINTS 4 float
0 0 0
1 0 0
0 1 0
0 0 1
POLYGONS 4 16
3 0 1 2
3 0 1 3
3 0 2 3
3 1 2 3
"""


def claimed_extensions(config: dict) -> list[str]:
    """Return the extensions claimed under the current configuration."""
    extensions = config.get('extensions') or {}
    return resolve_extensions(extensions.get('add'), extensions.get('remove'))


def cmd_preview(args: argparse.Namespace) -> int:
    """Render a file and print the path of the cached PNG preview."""
    config = config_mod.load()
    if args.no_cache:
        config['cache'] = False
    try:
        out = render_mod.preview(args.path, config)
    except render_mod.RenderError as error:
        print(error, file=sys.stderr)
        return 1
    if args.output:
        shutil.copyfile(out, args.output)
        out = Path(args.output)
    print(out)
    return 0


def cmd_daemon(_: argparse.Namespace) -> int:
    """Run the render service in the foreground."""
    return daemon_mod.serve()


def cmd_service(args: argparse.Namespace) -> int:
    """Install, remove, or report on the render service."""
    label = daemon_mod.LABEL
    target = f'gui/{os.getuid()}/{label}'
    path = daemon_mod.agent_path()

    if args.uninstall:
        subprocess.run(['/bin/launchctl', 'bootout', target], capture_output=True, check=False)
        path.unlink(missing_ok=True)
        print(f'removed {label}')
        return 0

    if args.install:
        helper = args.helper or shutil.which('pvql') or str(Path.home() / '.local/bin/pvql')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('wb') as handle:
            plistlib.dump(daemon_mod.agent_plist(helper), handle, sort_keys=False)
        subprocess.run(['/bin/launchctl', 'bootout', target], capture_output=True, check=False)
        loaded = subprocess.run(
            ['/bin/launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if loaded.returncode != 0:
            print(f'could not load {label}: {loaded.stderr.strip()}', file=sys.stderr)
            return 1
        subprocess.run(
            ['/bin/launchctl', 'kickstart', '-k', target], capture_output=True, check=False
        )
        print(f'installed {path}')
        return 0

    print(_run(['/bin/launchctl', 'print', target]) or f'{label} is not loaded')
    return 0


def cmd_warm(args: argparse.Namespace) -> int:
    """Render previews ahead of time for the given files or directories."""
    config = config_mod.load()
    claimed = set(claimed_extensions(config))
    targets: list[Path] = []
    for entry in args.paths:
        path = Path(entry).expanduser()
        if path.is_dir():
            targets += [p for p in sorted(path.rglob('*')) if p.suffix.lower() in claimed]
        elif path.is_file():
            targets.append(path)
    failures = 0
    for target in targets:
        try:
            render_mod.preview(target, config)
        except render_mod.RenderError as error:  # noqa: PERF203
            failures += 1
            print(f'✗ {target}: {str(error).splitlines()[0]}', file=sys.stderr)
        else:
            print(f'✓ {target}')
    print(f'{len(targets) - failures} of {len(targets)} cached')
    return 1 if failures else 0


def cmd_types(args: argparse.Namespace) -> int:
    """List the file extensions the Quick Look extension claims."""
    config = config_mod.load()
    claimed = claimed_extensions(config)
    listing = sorted(FORMATS) if args.all else claimed
    for ext in listing:
        mark = '✓' if ext in claimed else ' '
        print(f'{mark} {ext:<10} {FORMATS[ext].description:<32} {uti_for(ext)}')
    if not args.all:
        print(f'\n{len(claimed)} extensions claimed. Use --all to see every known format.')
    return 0


def cmd_plist(args: argparse.Namespace) -> int:
    """Write the Info.plist files used when building the app bundle."""
    config = config_mod.load()
    extensions = claimed_extensions(config)
    helper = args.helper or shutil.which('pvql')
    if args.app:
        plist_mod.write(plist_mod.app_plist(extensions, helper), args.app)
        print(args.app)
    if args.extension:
        plist_mod.write(plist_mod.extension_plist(extensions, helper), args.extension)
        print(args.extension)
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Show the configuration, or write a fresh one with discovered defaults."""
    if args.init:
        config = config_mod.load()
        config['pyvista'] = args.pyvista or config.get('pyvista') or config_mod.find_pyvista()
        config['pvql'] = args.helper or config.get('pvql') or shutil.which('pvql')
        path = config_mod.save(config)
        print(f'wrote {path}')
    print(config_mod.CONFIG_PATH)
    if config_mod.CONFIG_PATH.is_file():
        print(config_mod.CONFIG_PATH.read_text().rstrip())
    else:
        print('(not created yet; run "pvql config --init")')
    return 0


def cmd_cache(args: argparse.Namespace) -> int:
    """Show or clear the preview cache."""
    if args.clear:
        print(f'removed {render_mod.clear_cache()} cached previews')
        return 0
    entries = list(config_mod.CACHE_DIR.glob('*.png')) if config_mod.CACHE_DIR.is_dir() else []
    total = sum(entry.stat().st_size for entry in entries)
    print(f'{config_mod.CACHE_DIR}\n{len(entries)} previews, {total / 1024 / 1024:.1f} MB')
    return 0


def _run(command: list[str]) -> str:
    """Run a command and return its combined output, or an empty string on failure."""
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ''
    return (completed.stdout + completed.stderr).strip()


def cmd_doctor(_: argparse.Namespace) -> int:
    """Check that every piece of the Quick Look integration is in place."""
    config = config_mod.load()
    problems = 0

    suffix = '' if config_mod.CONFIG_PATH.is_file() else '  (using defaults)'
    print(f'config       {config_mod.CONFIG_PATH}{suffix}')
    print(f'cache        {config_mod.CACHE_DIR}')

    executable = config_mod.find_pyvista(config.get('pyvista'))
    if executable:
        print(f'✓ pyvista    {executable}')
    else:
        problems += 1
        print('✗ pyvista    not found; set "pyvista" in the config file')

    print(f'✓ formats    {len(claimed_extensions(config))} extensions claimed')

    installed = [
        candidate
        for candidate in (
            Path.home() / 'Applications' / f'{plist_mod.APP_EXECUTABLE}.app',
            Path('/Applications') / f'{plist_mod.APP_EXECUTABLE}.app',
        )
        if candidate.is_dir()
    ]
    if installed:
        for candidate in installed:
            print(f'✓ app        {candidate}')
    else:
        problems += 1
        print('✗ app        not installed; run scripts/install.sh')

    registered = _run(['/usr/bin/pluginkit', '-m', '-i', plist_mod.EXT_BUNDLE_ID])
    if registered:
        print(f'✓ extension  registered ({registered})')
    else:
        problems += 1
        print('✗ extension  not registered with pluginkit')

    target = f'gui/{os.getuid()}/{daemon_mod.LABEL}'
    if _run(['/bin/launchctl', 'print', target]):
        print(f'✓ service    {daemon_mod.LABEL} loaded')
    else:
        problems += 1
        print('✗ service    not loaded; run "pvql service --install"')

    if executable:
        with tempfile.TemporaryDirectory() as scratch:
            sample = Path(scratch) / 'pvql-doctor.vtk'
            sample.write_text(SMOKE_MESH)
            started = time.monotonic()
            try:
                out = daemon_mod.request_preview(sample, timeout=90)
            except render_mod.RenderError as error:
                problems += 1
                print(f'✗ render     failed through the service\n\n{error}')
            else:
                elapsed = time.monotonic() - started
                size_kb = out.stat().st_size / 1024
                kind = 'interactive scene' if out.suffix == '.ply' else 'rendered image'
                print(f'✓ preview    {kind}, {size_kb:.0f} KB in {elapsed:.1f} s')
                out.unlink(missing_ok=True)

    print('\nall checks passed' if not problems else f'\n{problems} problem(s) found')
    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the ``pvql`` command."""
    parser = argparse.ArgumentParser(prog='pvql', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    preview = sub.add_parser('preview', help='render a file and print the cached PNG path')
    preview.add_argument('path')
    preview.add_argument('-o', '--output', help='also copy the preview to this path')
    preview.add_argument('--no-cache', action='store_true', help='ignore any cached preview')
    preview.set_defaults(func=cmd_preview)

    daemon = sub.add_parser('daemon', help='run the render service in the foreground')
    daemon.set_defaults(func=cmd_daemon)

    service = sub.add_parser('service', help='install or remove the render service')
    service.add_argument('--install', action='store_true')
    service.add_argument('--uninstall', action='store_true')
    service.add_argument('--helper', help='absolute path to the pvql executable')
    service.set_defaults(func=cmd_service)

    warm = sub.add_parser('warm', help='render previews ahead of time')
    warm.add_argument('paths', nargs='+')
    warm.set_defaults(func=cmd_warm)

    types = sub.add_parser('types', help='list claimed file extensions')
    types.add_argument('--all', action='store_true', help='include formats that are not claimed')
    types.set_defaults(func=cmd_types)

    plist = sub.add_parser('plist', help='write Info.plist files for the app bundle')
    plist.add_argument('--app')
    plist.add_argument('--extension')
    plist.add_argument('--helper', help='absolute path to the pvql executable')
    plist.set_defaults(func=cmd_plist)

    config = sub.add_parser('config', help='show or create the configuration file')
    config.add_argument('--init', action='store_true', help='write a configuration file')
    config.add_argument('--pyvista', help='absolute path to the pyvista executable')
    config.add_argument('--helper', help='absolute path to the pvql executable')
    config.set_defaults(func=cmd_config)

    cache = sub.add_parser('cache', help='show or clear the preview cache')
    cache.add_argument('--clear', action='store_true')
    cache.set_defaults(func=cmd_cache)

    doctor = sub.add_parser('doctor', help='check the Quick Look integration')
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the ``pvql`` command-line interface."""
    args = build_parser().parse_args(argv)
    return args.func(args)
