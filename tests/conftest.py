"""Shared test configuration."""

from __future__ import annotations

import pytest


def has_rendering() -> bool:
    """Return whether the VTK fork's rendering modules are installed."""
    try:
        from pyvista._vtk import vtkRenderWindow  # noqa: F401
    except ImportError:
        return False
    return True


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip tests marked ``needs_rendering`` where cvista ships no rendering wheel."""
    if has_rendering():
        return
    skip = pytest.mark.skip(reason='cvista ships no rendering wheel for this Python')
    for item in items:
        if item.get_closest_marker('needs_rendering'):
            item.add_marker(skip)
