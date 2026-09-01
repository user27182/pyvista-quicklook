"""Convert a mesh file into a coloured PLY that SceneKit can display.

This module is run by the PyVista interpreter, not by ``pvql`` itself, so it
imports only PyVista and its own dependencies.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pyvista as pv


def to_surface(dataset: object) -> pv.PolyData:
    """Return a triangulated surface for any dataset PyVista can read."""
    if isinstance(dataset, pv.MultiBlock):
        dataset = dataset.combine()
    surface = dataset.extract_surface() if hasattr(dataset, 'extract_surface') else dataset
    if not isinstance(surface, pv.PolyData):
        surface = surface.extract_geometry()
    return surface.triangulate()


def has_cell_scalars(surface: pv.PolyData) -> bool:
    """Return whether the active scalars sit on cells rather than points."""
    name = surface.active_scalars_name
    return bool(name) and name in surface.cell_data


def to_point_scalars(surface: pv.PolyData) -> pv.PolyData:
    """Return a surface carrying cell scalars on points, one cell per point."""
    if not has_cell_scalars(surface):
        return surface
    separated = surface.separate_cells().cell_data_to_point_data()
    return separated.extract_surface(algorithm='dataset_surface').triangulate()


def colours_for(surface: pv.PolyData, colormap: str) -> np.ndarray | None:
    """Return per-point RGB for the active scalars, or None when there are none."""
    scalars = surface.active_scalars
    if scalars is None:
        return None

    scalars = np.asarray(scalars)
    if scalars.ndim == 2:
        if scalars.shape[1] >= 3 and scalars.dtype == np.uint8:
            return scalars[:, :3]
        scalars = np.linalg.norm(scalars, axis=1)

    if scalars.ndim != 1 or scalars.size != surface.n_points:
        return None

    from matplotlib import colormaps

    finite = scalars[np.isfinite(scalars)]
    if finite.size == 0:
        return None
    low, high = float(finite.min()), float(finite.max())
    span = high - low if high > low else 1.0
    normalised = np.clip((np.nan_to_num(scalars, nan=low) - low) / span, 0.0, 1.0)
    return (colormaps[colormap](normalised)[:, :3] * 255).astype(np.uint8)


def export(source: str, destination: str, max_points: int, colormap: str) -> None:
    """Write a mesh file out as a PLY with vertex colours."""
    surface = to_surface(pv.read(source))
    if surface.n_points == 0:
        message = 'the dataset has no surface to show'
        raise ValueError(message)

    # Splitting cells triples the points, so the cap is shared out beforehand.
    cap = max_points // 3 if max_points and has_cell_scalars(surface) else max_points
    if cap and surface.n_points > cap:
        ratio = 1.0 - (cap / surface.n_points)
        surface = surface.decimate_pro(ratio, preserve_topology=True).triangulate()

    surface = to_point_scalars(surface)
    colours = colours_for(surface, colormap)
    surface.clear_data()
    if colours is not None and len(colours) == surface.n_points:
        surface['RGB'] = colours
        surface.save(destination, texture='RGB')
    else:
        surface.save(destination)


def main() -> int:
    """Run the converter from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--max-points', type=int, default=2_000_000)
    parser.add_argument('--colormap', default='viridis')
    args = parser.parse_args()
    export(args.source, args.destination, args.max_points, args.colormap)
    return 0


if __name__ == '__main__':
    sys.exit(main())
