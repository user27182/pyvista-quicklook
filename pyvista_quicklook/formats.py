"""File extensions claimed by the Quick Look extension."""

from __future__ import annotations

from typing import NamedTuple

UTI_PREFIX = 'io.github.user27182.pyvista-quicklook'


class Format(NamedTuple):
    """A file extension, its human-readable name, and whether it is claimed by default."""

    description: str
    default: bool


# Extensions ``pyvista.read`` supports, with pyvista-cad's readers. ``default=False``
# entries are claimed only when listed in the ``extensions.add`` config key. Formats
# macOS previews itself (STL, OBJ, PLY, glTF, images, DICOM) and extensions another
# type owns (.img, .raw, .xml) are absent: Launch Services keeps its own type for
# those, so a claim has no effect.
FORMATS: dict[str, Format] = {
    # VTK serial formats
    '.vtk': Format('VTK Legacy Data', True),
    '.vti': Format('VTK Image Data', True),
    '.vtr': Format('VTK Rectilinear Grid', True),
    '.vts': Format('VTK Structured Grid', True),
    '.vtp': Format('VTK PolyData', True),
    '.vtu': Format('VTK Unstructured Grid', True),
    '.vtm': Format('VTK MultiBlock', True),
    '.vtmb': Format('VTK MultiBlock', True),
    '.vtpd': Format('VTK Partitioned Dataset', True),
    '.vtkhdf': Format('VTK HDF', True),
    # VTK parallel formats
    '.pvtk': Format('VTK Parallel Legacy Data', True),
    '.pvti': Format('VTK Parallel Image Data', True),
    '.pvtr': Format('VTK Parallel Rectilinear Grid', True),
    '.pvtu': Format('VTK Parallel Unstructured Grid', True),
    '.pvd': Format('ParaView Data Collection', True),
    '.xdmf': Format('XDMF Data', True),
    # Simulation and CFD formats
    '.case': Format('EnSight Case', True),
    '.exo': Format('Exodus II Data', True),
    '.ex2': Format('Exodus II Data', True),
    '.exii': Format('Exodus II Data', True),
    '.foam': Format('OpenFOAM Case', True),
    '.cgns': Format('CGNS Data', True),
    '.nek5000': Format('Nek5000 Data', True),
    '.p3d': Format('PLOT3D Metadata', True),
    '.cas': Format('Fluent Case', True),
    '.frd': Format('CalculiX Result', True),
    '.neu': Format('GAMBIT Neutral Mesh', True),
    '.grdecl': Format('Eclipse GRDECL Grid', True),
    # Geometry, volume and misc formats
    '.facet': Format('Facet Surface', True),
    '.slc': Format('SLC Volume', True),
    '.dem': Format('Digital Elevation Model', True),
    '.cube': Format('Gaussian Cube', True),
    '.pdb': Format('Protein Data Bank', True),
    '.segy': Format('SEG-Y Seismic Data', True),
    '.sgy': Format('SEG-Y Seismic Data', True),
    '.tri': Format('BYU Triangle Surface', True),
    '.3ds': Format('3D Studio Model', True),
    '.wrl': Format('VRML Model', True),
    '.vrml': Format('VRML Model', True),
    # CAD formats, read by pyvista-cad.
    '.step': Format('STEP Model', True),
    '.stp': Format('STEP Model', True),
    '.dxf': Format('DXF Drawing', True),
    '.3mf': Format('3MF Model', True),
    # Mesh formats read by meshio.
    '.avs': Format('AVS UCD Mesh', True),
    '.bdf': Format('Nastran Bulk Data', True),
    '.f3grid': Format('FLAC3D Grid', True),
    '.fem': Format('Nastran Bulk Data', True),
    '.mdpa': Format('Kratos Model Part', True),
    '.mesh': Format('Medit Mesh', True),
    '.meshb': Format('Medit Binary Mesh', True),
    '.nas': Format('Nastran Bulk Data', True),
    '.off': Format('Object File Format Mesh', True),
    '.tec': Format('Tecplot ASCII Data', True),
    '.vol': Format('Netgen Mesh', True),
    # Off by default: extensions meshio reads but that other tools use too.
    '.msh': Format('Gmsh Mesh', False),
    '.dato': Format('PERMAS Data', False),
    '.post': Format('PERMAS Result', False),
    '.node': Format('TetGen Nodes', False),
    '.ele': Format('TetGen Elements', False),
    # Off by default: these readers need CAD kernels the installer leaves out.
    '.iges': Format('IGES Model', False),
    '.igs': Format('IGES Model', False),
    '.brep': Format('BREP Model', False),
    '.brp': Format('BREP Model', False),
    '.fcstd': Format('FreeCAD Document', False),
    '.ifc': Format('IFC Building Model', False),
    '.scad': Format('OpenSCAD Script', False),
    # Off by default: medical formats other viewers usually claim.
    '.nii': Format('NIfTI Volume', False),
    '.mha': Format('MetaImage Volume', False),
    '.mhd': Format('MetaImage Volume', False),
    '.nrrd': Format('NRRD Volume', False),
    '.nhdr': Format('NRRD Header', False),
    '.mnc': Format('MINC Volume', False),
    '.mr': Format('MR Image', False),
    # Off by default: extensions too generic to claim safely.
    '.dat': Format('Tecplot Data', False),
    '.h5': Format('HDF5 Data', False),
    '.hdf': Format('HDF Data', False),
    '.vrt': Format('GDAL Virtual Raster', False),
    '.inp': Format('AVS UCD Data', False),
    '.res': Format('Fluent Result', False),
    '.pts': Format('Point Cloud', False),
    '.series': Format('VTK File Series', False),
    '.g': Format('BYU Geometry', False),
    '.e': Format('Exodus II Data', False),
}


def uti_for(ext: str) -> str:
    """Return the exported uniform type identifier for an extension."""
    return f'{UTI_PREFIX}.{ext.lstrip(".").replace(".", "-")}'


def default_extensions() -> list[str]:
    """Return the extensions claimed unless the config overrides them."""
    return sorted(ext for ext, fmt in FORMATS.items() if fmt.default)


def resolve_extensions(add: list[str] | None = None, remove: list[str] | None = None) -> list[str]:
    """Return the claimed extensions after applying config additions and removals."""
    claimed = set(default_extensions())
    claimed |= {normalize(e) for e in add or []}
    claimed -= {normalize(e) for e in remove or []}
    return sorted(claimed)


def normalize(ext: str) -> str:
    """Return an extension lowercased and prefixed with a single dot."""
    return '.' + ext.strip().lstrip('.').lower()
