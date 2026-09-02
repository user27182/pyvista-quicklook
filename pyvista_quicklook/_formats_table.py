"""Build the README's format tables from PyVista's reader tables.

This module is run by the PyVista interpreter, not by ``pvql`` itself:
``python -m pyvista_quicklook._formats_table README.md`` rewrites the tables in place.
"""

from __future__ import annotations

from itertools import zip_longest
from pathlib import Path
import sys
from typing import NamedTuple

import meshio
from pyvista.core.utilities.reader import CLASS_READERS
from pyvista.core.utilities.reader_registry import registered_readers

from .formats import FORMATS
from .formats import Format

START = '## Supported files\n'
END = 'macOS previews STL'


class Row(NamedTuple):
    """One format: its name, the extensions one reader takes, and why it is off, if it is."""

    name: str
    extensions: list[str]
    default: bool
    reason: str


def reader_of(ext: str) -> str:
    """Return what reads an extension: a VTK reader class, a plugin, or meshio's format."""
    for entry in registered_readers():
        if entry.extension == ext:
            return entry.source
    if ext in CLASS_READERS:
        return CLASS_READERS[ext].__name__
    return 'meshio:' + ','.join(meshio.extension_to_filetypes[ext])


def rows() -> list[Row]:
    """Return one row per reader, split by whether its extensions are claimed by default."""
    grouped: dict[tuple[str, bool], list[str]] = {}
    for ext, fmt in FORMATS.items():
        grouped.setdefault((reader_of(ext), fmt.default), []).append(ext)
    result = []
    for (_, default), extensions in grouped.items():
        formats: list[Format] = [FORMATS[ext] for ext in extensions]
        names = {fmt.description for fmt in formats}
        reasons = {fmt.reason for fmt in formats}
        if len(names) > 1 or len(reasons) > 1:
            message = f'{extensions} share a reader but not a description and reason'
            raise ValueError(message)
        result.append(Row(names.pop(), sorted(extensions), default, reasons.pop()))
    return sorted(result, key=lambda row: row.name.lower())


def section() -> str:
    """Return the README text between the Supported files heading and the closing note."""
    claimed = [row for row in rows() if row.default]
    optional = [row for row in rows() if not row.default]

    def cell(row: Row) -> str:
        return ', '.join(f'`{ext}`' for ext in row.extensions)

    def pair(left: Row, right: Row | None) -> str:
        tail = f' {right.name} | {cell(right)} |' if right else ' | |'
        return f'| {left.name} | {cell(left)} |{tail}'

    half = (len(claimed) + 1) // 2
    lines = [
        '',
        (
            f'{sum(len(r.extensions) for r in claimed)} extensions are claimed by default, so'
            ' pressing space on any of them opens this'
        ),
        'preview:',
        '',
        '| Format | Extensions | Format | Extensions |',
        '| --- | --- | --- | --- |',
        *(pair(left, right) for left, right in zip_longest(claimed[:half], claimed[half:])),
        '',
        f'{sum(len(r.extensions) for r in optional)} more can be claimed with `extensions.add`:',
        '',
        '| Format | Extensions | Why not by default |',
        '| --- | --- | --- |',
        *(f'| {row.name} | {cell(row)} | {row.reason} |' for row in optional),
        '',
        '',
    ]
    return '\n'.join(lines)


def rewrite(readme: Path) -> None:
    """Replace the tables in a README with freshly generated ones."""
    text = readme.read_text()
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    readme.write_text(head + START + section() + END + tail)


if __name__ == '__main__':
    rewrite(Path(sys.argv[1]))
