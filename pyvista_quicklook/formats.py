"""File extensions claimed by the Quick Look extension."""

from __future__ import annotations

from typing import NamedTuple

UTI_PREFIX = 'io.github.user27182.pyvista-quicklook'


class Format(NamedTuple):
    """A file extension, its human-readable name, and whether it is claimed by default."""

    description: str
    default: bool
    reason: str = ''
    """Why the extension is not claimed by default."""


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
    # Zstandard-compressed VTK, written by pyvista-zstd.
    '.pv': Format('PyVista Zstandard Data', True),
    '.zvtk': Format('PyVista Zstandard Data', True),
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
    '.tri': Format('Binary Marching Cubes Surface', True),
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
    '.meshb': Format('Medit Mesh', True),
    '.nas': Format('Nastran Bulk Data', True),
    '.off': Format('Object File Format Mesh', True),
    '.tec': Format('Tecplot ASCII Data', True),
    '.vol': Format('Netgen Mesh', True),
    # Off by default: extensions meshio reads but that other tools use too.
    '.msh': Format(
        'Gmsh Mesh',
        False,
        'the extension is shared with ANSYS meshes, and meshio reads only the binary Gmsh form',
    ),
    '.dato': Format('PERMAS Data', False, 'the extension is shared with other kinds of file'),
    '.post': Format('PERMAS Data', False, 'the extension is shared with other kinds of file'),
    '.node': Format('TetGen Mesh', False, 'each is half of a TetGen pair'),
    '.ele': Format('TetGen Mesh', False, 'each is half of a TetGen pair'),
    # Off by default: these readers need CAD kernels the installer leaves out.
    '.iges': Format(
        'IGES Model', False, 'needs `pyvista-cad[step]`, the OpenCascade kernel, about 200 MB more'
    ),
    '.igs': Format(
        'IGES Model', False, 'needs `pyvista-cad[step]`, the OpenCascade kernel, about 200 MB more'
    ),
    '.brep': Format(
        'BREP Model', False, 'needs `pyvista-cad[step]`, the OpenCascade kernel, about 200 MB more'
    ),
    '.brp': Format(
        'BREP Model', False, 'needs `pyvista-cad[step]`, the OpenCascade kernel, about 200 MB more'
    ),
    '.fcstd': Format(
        'FreeCAD Document',
        False,
        'needs `pyvista-cad[step]`, the OpenCascade kernel, about 200 MB more',
    ),
    '.ifc': Format('IFC Building Model', False, 'needs `pyvista-cad[ifc]`'),
    '.scad': Format('OpenSCAD Script', False, 'needs the `openscad` program'),
    # Medical volumes
    '.nii': Format('NIfTI Volume', True),
    '.mha': Format('MetaImage Volume', True),
    '.mhd': Format('MetaImage Volume', True),
    '.nrrd': Format('NRRD Volume', True),
    '.nhdr': Format('NRRD Volume', True),
    '.mnc': Format('MINC Volume', True),
    '.mr': Format('GE Signa MR Image', True),
    # Off by default: extensions too generic to claim safely.
    '.dat': Format('Tecplot Data', False, 'the extension is shared with other kinds of file'),
    '.h5': Format('Fluent CFF Data', False, 'the extension is shared with other kinds of file'),
    '.hdf': Format('VTK HDF', False, 'the extension is shared with other kinds of file'),
    '.vrt': Format('ProStar Mesh', False, 'the extension is shared with other kinds of file'),
    '.inp': Format('AVS UCD Data', False, 'the extension is shared with other kinds of file'),
    '.res': Format('MFIX Result', False, 'the extension is shared with other kinds of file'),
    '.pts': Format('Point Cloud', False, 'the extension is shared with other kinds of file'),
    '.series': Format(
        'VTK File Series', False, 'the extension is shared with other kinds of file'
    ),
    '.g': Format('BYU Geometry', False, 'the extension is shared with other kinds of file'),
    '.e': Format('Exodus II Data', False, 'the extension is shared with other kinds of file'),
}


# Extensions the environment can read that are deliberately not claimed, and why.
UNCLAIMED: dict[str, str] = {
    # macOS previews these itself, and Launch Services keeps its own type for them.
    '.stl': 'macOS previews it',
    '.obj': 'macOS previews it',
    '.ply': 'macOS previews it',
    '.glb': 'macOS previews it',
    '.gltf': 'macOS previews it',
    '.bmp': 'macOS previews it',
    '.gif': 'macOS previews it',
    '.hdr': 'macOS previews it',
    '.jpeg': 'macOS previews it',
    '.jpg': 'macOS previews it',
    '.png': 'macOS previews it',
    '.pnm': 'macOS previews it',
    '.tif': 'macOS previews it',
    '.tiff': 'macOS previews it',
    '.dcm': 'macOS previews it',
    # Launch Services gives the extension to another kind of file.
    '.img': 'disk images own the extension',
    '.raw': 'camera raw images own the extension',
    '.xml': 'XML owns the extension',
    # The Finder sees only the last suffix.
    '.dato.gz': 'the Finder sees .gz',
    '.nii.gz': 'the Finder sees .gz',
    '.post.gz': 'the Finder sees .gz',
    '.vol.gz': 'the Finder sees .gz',
    # meshio lists these but cannot read them as installed.
    '.h5m': 'needs h5py',
    '.hmf': 'needs h5py',
    '.med': 'needs h5py',
    '.xmf': 'needs h5py',
    '.su2': 'meshio fails to read it',
    '.ugrid': 'meshio fails to read it',
    '.wkt': 'meshio hangs on it',
    '.svg': 'meshio writes it but does not read it',
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
