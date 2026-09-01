"""Import PyVista and VTK and exercise both preview paths.

This module is run by the PyVista interpreter, not by ``pvql`` itself, so it
imports only PyVista and its own dependencies.
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


def import_vtk_modules() -> None:
    """Load every VTK module, so none of them is paged in during a preview."""
    try:
        from pyvista._vtk import import_all
    except ImportError:
        return
    import_all()


def main() -> int:
    """Warm the modules and caches that a preview needs."""
    import_vtk_modules()

    import pyvista as pv

    mesh = pv.Sphere(theta_resolution=8, phi_resolution=8).elevation()
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        # The interactive path: extract a surface and write it out.
        mesh.extract_surface().triangulate().save(directory / 'warm.ply')
        # The still-image path, absent from builds without the rendering modules.
        try:
            plotter = pv.Plotter(off_screen=True, window_size=(64, 64))
        except Exception:  # noqa: BLE001
            return 0
        plotter.add_mesh(mesh)
        plotter.screenshot(str(directory / 'warm.png'))
        plotter.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
