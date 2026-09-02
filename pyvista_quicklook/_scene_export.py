"""Convert a mesh file into a coloured PLY that SceneKit can display.

This module is run by the PyVista interpreter, not by ``pvql`` itself, so it
imports only PyVista and its own dependencies.
"""

from __future__ import annotations

import argparse
import math
import sys

import numpy as np
import pyvista as pv


def skin_estimate(dimensions: tuple[int, int, int]) -> int:
    """Return roughly how many points the outer surface of a structured dataset has."""
    extents = [k for k in dimensions if k > 1]
    if len(extents) == 3:
        a, b, c = extents
        return 2 * (a * b + b * c + a * c)
    return math.prod(extents)


def thin(dataset: object, max_points: int) -> object:
    """Stride structured data down to the budget; decimating it would take minutes."""
    if not max_points or not hasattr(dataset, 'extract_subset'):
        return dataset
    budget = max_points // 3 if has_cell_scalars(dataset) else max_points
    expected = skin_estimate(dataset.dimensions)
    if expected <= budget:
        return dataset
    axes = sum(1 for k in dataset.dimensions if k > 1)
    stride = math.ceil((expected / budget) ** (1 / min(axes, 2)))
    nx, ny, nz = dataset.dimensions
    return dataset.extract_subset(voi=(0, nx - 1, 0, ny - 1, 0, nz - 1), rate=(stride,) * 3)


def to_surface(dataset: object) -> pv.PolyData:
    """Return the surface of any dataset PyVista can read, cells left as they are."""
    if isinstance(dataset, pv.PartitionedDataSet):
        dataset = pv.MultiBlock(list(dataset))
    if isinstance(dataset, pv.MultiBlock):
        dataset = dataset.combine()
    surface = (
        dataset.extract_surface(algorithm='dataset_surface')
        if hasattr(dataset, 'extract_surface')
        else dataset
    )
    if not isinstance(surface, pv.PolyData):
        surface = surface.extract_geometry()
    return surface


# Viridis at 32 control points, interpolated to a full ramp.
_VIRIDIS = (
    '440154470d6048186a482475472e7c4538824241863e4c8a3a548c365d8d32658e2e6d8e2b758e'
    '287d8e25848e228c8d1f948c1e9c8920a38625ab822eb37c3aba7648c16e58c76569cd5b7fd34e'
    '93d741a8db34bddf26d5e21aeae51afde725'
)


def ramp() -> np.ndarray:
    """Return the 256-entry RGB table previews are coloured with."""
    control = np.frombuffer(bytes.fromhex(_VIRIDIS), dtype=np.uint8).reshape(-1, 3)
    positions = np.linspace(0, 255, len(control))
    channels = [np.interp(np.arange(256), positions, control[:, c]) for c in range(3)]
    return np.stack(channels, axis=1).round().astype(np.uint8)


def solidify(surface: pv.PolyData, max_glyphs: int) -> pv.PolyData:
    """Give lines and loose points a surface, so there is something to draw."""
    if surface.n_faces:
        return surface

    size = surface.length or 1.0
    if surface.n_lines:
        tubed = surface.tube(radius=size * 0.004, n_sides=8).triangulate()
        # tube() names its normals differently from everything that reads them.
        if 'TubeNormals' in tubed.point_data:
            tubed.point_data['Normals'] = tubed.point_data['TubeNormals']
            tubed.point_data.active_normals_name = 'Normals'
        return tubed

    if surface.n_points:
        points = surface
        if max_glyphs and surface.n_points > max_glyphs:
            step = surface.n_points // max_glyphs + 1
            kept = np.arange(0, surface.n_points, step)
            points = surface.extract_points(kept).extract_surface(algorithm='dataset_surface')
        # Scale with the spacing between points, so a handful of them still read.
        spacing = size / max(points.n_points, 1) ** (1 / 3)
        radius = min(size * 0.2, spacing * 0.15)
        sphere = pv.Sphere(radius=radius, theta_resolution=6, phi_resolution=6)
        return points.glyph(geom=sphere, scale=False, orient=False).triangulate()

    return surface


def recentre(surface: pv.PolyData) -> pv.PolyData:
    """Move the mesh to the origin, so far-from-origin coordinates keep their precision."""
    return surface.translate(-np.array(surface.center), inplace=False)


def choose_scalars(surface: pv.PolyData) -> pv.PolyData:
    """Point the surface away from VTK's bookkeeping arrays, colouring by a real one."""
    name = surface.active_scalars_name
    if not name:
        # Nothing was active, so the file asks for no colour. Leave it that way.
        return surface
    if not name.startswith('vtk'):
        return surface
    for source in (surface.point_data, surface.cell_data):
        for candidate in source:
            if not candidate.startswith('vtk'):
                surface.set_active_scalars(candidate)
                return surface
    surface.set_active_scalars(None)
    return surface


def has_cell_scalars(dataset: pv.DataSet) -> bool:
    """Return whether the active scalars sit on cells rather than points."""
    name = dataset.active_scalars_name
    return bool(name) and name in dataset.cell_data


def to_point_scalars(surface: pv.PolyData) -> pv.PolyData:
    """Return a surface carrying cell scalars on points, one cell per point."""
    if not has_cell_scalars(surface):
        return surface
    separated = surface.separate_cells().cell_data_to_point_data()
    return separated.extract_surface(algorithm='dataset_surface').triangulate()


def colours_for(surface: pv.PolyData) -> np.ndarray | None:
    """Return per-point RGB for the active scalars, or None when there are none."""
    scalars = surface.active_scalars
    if scalars is None:
        return None

    scalars = np.asarray(scalars)
    if scalars.dtype.kind not in 'biuf':
        return None
    if scalars.ndim == 2:
        if scalars.shape[1] >= 3 and scalars.dtype == np.uint8:
            return scalars[:, :3]
        scalars = np.linalg.norm(scalars, axis=1)

    if scalars.ndim != 1 or scalars.size != surface.n_points:
        return None

    finite = scalars[np.isfinite(scalars)]
    if finite.size == 0:
        return None
    low, high = float(finite.min()), float(finite.max())
    span = high - low if high > low else 1.0
    normalised = np.clip((np.nan_to_num(scalars, nan=low) - low) / span, 0.0, 1.0)
    return ramp()[(normalised * 255).round().astype(np.intp)]


def export(source: str, destination: str, max_points: int, max_glyphs: int) -> None:
    """Write a mesh file out as a PLY with vertex colours; a budget of zero is no cap."""
    # Triangulating first would discard the vertex and line cells solidify needs.
    surface = choose_scalars(to_surface(thin(pv.read(source), max_points)))
    wanted = surface.active_scalars_name
    surface = solidify(surface, max_glyphs).triangulate()
    # tube() and glyph() add arrays of their own; colour only by what the file had.
    surface.set_active_scalars(wanted if wanted in surface.array_names else None)
    if surface.n_points == 0:
        message = 'the dataset has no surface to show'
        raise ValueError(message)

    # Splitting cells triples the points, so the cap is shared out beforehand.
    cap = max_points // 3 if max_points and has_cell_scalars(surface) else max_points
    if cap and surface.n_points > cap:
        ratio = 1.0 - (cap / surface.n_points)
        surface = surface.decimate_pro(ratio, preserve_topology=True).triangulate()

    surface = recentre(to_point_scalars(surface))
    colours = colours_for(surface)
    normals = np.array(surface.point_data['Normals']) if 'Normals' in surface.point_data else None
    surface.clear_data()
    if normals is not None and len(normals) == surface.n_points:
        surface.point_data['Normals'] = normals
        surface.point_data.active_normals_name = 'Normals'
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
    parser.add_argument('--max-points', type=int, required=True)
    parser.add_argument('--max-glyphs', type=int, required=True)
    args = parser.parse_args()
    export(args.source, args.destination, args.max_points, args.max_glyphs)
    return 0


if __name__ == '__main__':
    sys.exit(main())
