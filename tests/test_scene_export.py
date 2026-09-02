"""Tests for the exporter."""

from __future__ import annotations

import meshio
import numpy as np
import pytest
import pyvista as pv
from pyvista.core.utilities import reader as readers
from pyvista.core.utilities import reader_registry
from pyvista_cad import examples as cad_examples

from pyvista_quicklook import _scene_export as export_mod
from pyvista_quicklook import formats


def written(mesh_or_path, tmp_path, name='out.ply', **kwargs):
    """Export a dataset and read the resulting PLY back."""
    source = tmp_path / 'in.vtk'
    if isinstance(mesh_or_path, (str,)):
        source = mesh_or_path
    else:
        mesh_or_path.save(source)
    destination = tmp_path / name
    export_mod.export(
        str(source),
        str(destination),
        kwargs.pop('max_points', 2_000_000),
        kwargs.pop('max_glyphs', 20_000),
        **kwargs,
    )
    return pv.read(destination)


def coloured(mesh):
    """Return whether a PLY read back carries vertex colours."""
    return any(name.lower() in {'rgb', 'red'} for name in mesh.array_names)


def test_a_surface_survives_with_its_faces(tmp_path):
    """An ordinary surface keeps its geometry."""
    out = written(pv.Sphere(theta_resolution=8, phi_resolution=8), tmp_path)
    assert out.n_points > 0
    assert out.n_faces > 0


def test_a_volume_becomes_its_boundary(tmp_path):
    """A volume is reduced to a surface rather than refused."""
    out = written(pv.Wavelet(), tmp_path)
    assert out.n_faces > 0


def test_a_point_cloud_becomes_glyphs(tmp_path):
    """Loose points are drawn as spheres, so the preview is not empty."""
    cloud = pv.PolyData(np.random.default_rng(0).random((200, 3)))
    assert cloud.n_faces == 0
    out = written(cloud, tmp_path, name='cloud.ply')
    assert out.n_faces > 0
    assert out.n_points > cloud.n_points


def bare_polyline():
    """Return a polyline carrying no data arrays of its own."""
    points = np.array([[0.0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 1]])
    return pv.PolyData(points, lines=np.array([4, 0, 1, 2, 3]))


def test_lines_become_tubes(tmp_path):
    """Line geometry is drawn as tubes, so the preview is not empty."""
    line = bare_polyline()
    assert line.n_faces == 0
    assert line.n_lines > 0
    out = written(line, tmp_path, name='line.ply')
    assert out.n_faces > 0


def test_glyphs_are_capped(tmp_path):
    """Only a budget of points is glyphed, however many the cloud holds."""
    cloud = pv.PolyData(np.random.default_rng(0).random((5000, 3)))
    small = written(cloud, tmp_path, name='small.ply', max_glyphs=50)
    large = written(cloud, tmp_path, name='large.ply', max_glyphs=500)
    assert small.n_points < large.n_points


def test_point_scalars_are_carried_as_colour(tmp_path):
    """A dataset with point scalars previews in colour."""
    mesh = pv.Sphere(theta_resolution=8, phi_resolution=8).elevation()
    out = written(mesh, tmp_path)
    assert coloured(out)


def test_cell_scalars_are_split_rather_than_averaged(tmp_path):
    """Cell scalars keep each face flat, which needs one set of points per cell."""
    mesh = pv.Sphere(theta_resolution=8, phi_resolution=8).triangulate()
    mesh.cell_data['region'] = (np.arange(mesh.n_cells) % 4).astype(float)
    mesh.set_active_scalars('region')
    out = written(mesh, tmp_path)
    assert coloured(out)
    assert out.n_points == mesh.n_cells * 3


def test_a_dataset_without_scalars_gets_no_colour(tmp_path):
    """A file that asks for no colour is drawn plain, as pyvista plot draws it."""
    mesh = pv.Sphere(theta_resolution=8, phi_resolution=8)
    assert mesh.active_scalars_name is None
    assert not coloured(written(mesh, tmp_path))


def test_filter_arrays_do_not_become_the_colour(tmp_path):
    """Arrays that tube() and glyph() add are not mistaken for the file's own."""
    assert not coloured(written(bare_polyline(), tmp_path, name='line.ply'))

    cloud = pv.PolyData(np.random.default_rng(0).random((100, 3)))
    assert not coloured(written(cloud, tmp_path, name='cloud.ply'))


def test_a_line_keeps_its_own_scalars(tmp_path):
    """A line that does carry scalars is still coloured by them."""
    line = pv.Line(pointa=(0, 0, 0), pointb=(1, 1, 1), resolution=10)
    assert line.active_scalars_name == 'Distance'
    assert coloured(written(line, tmp_path, name='line.ply'))


def test_normals_are_not_mistaken_for_scalars(tmp_path):
    """A mesh carrying only normals is drawn plain."""
    mesh = pv.Sphere(theta_resolution=8, phi_resolution=8).compute_normals()
    mesh.set_active_scalars(None)
    assert not coloured(written(mesh, tmp_path))


def test_vtk_bookkeeping_arrays_are_stepped_over(tmp_path):
    """An active vtk array yields to a real one rather than breaking the export."""
    mesh = pv.Sphere(theta_resolution=8, phi_resolution=8).triangulate()
    mesh.cell_data['vtkGhostType'] = np.zeros(mesh.n_cells, np.uint8)
    mesh.cell_data['region'] = (np.arange(mesh.n_cells) % 3).astype(float)
    mesh.set_active_scalars('vtkGhostType')
    out = written(mesh, tmp_path)
    assert coloured(out)


def test_the_result_is_centred(tmp_path):
    """Coordinates are moved to the origin, so distant datasets keep their precision."""
    mesh = pv.Sphere(theta_resolution=8, phi_resolution=8)
    mesh.points += 1.0e7
    out = written(mesh, tmp_path)
    assert np.allclose(out.center, 0, atol=max(1.0, out.length * 1e-3))


def test_an_empty_dataset_is_reported(tmp_path):
    """A dataset with nothing in it says so instead of writing an empty scene."""
    with pytest.raises(ValueError, match='no surface'):
        written(pv.PolyData(), tmp_path)


def test_the_ramp_matches_viridis_ends():
    """The built-in colour table spans viridis from dark blue to yellow."""
    table = export_mod.ramp()
    assert table.shape == (256, 3)
    assert tuple(table[0]) == (68, 1, 84)
    assert tuple(table[-1]) == (253, 231, 37)


def test_glyph_size_follows_point_spacing():
    """Sparse clouds get larger spheres, so a handful of points still reads."""
    rng = np.random.default_rng(0)
    corners = np.array([[0.0, 0, 0], [1.0, 1, 1]])
    sparse = pv.PolyData(np.vstack([corners, [[0.5, 0.5, 0.5]]]))
    dense = pv.PolyData(np.vstack([corners, rng.random((3000, 3))]))

    # The spheres reach past the points they sit on, further when there are fewer.
    sparse_reach = export_mod.solidify(sparse, 20_000).length - sparse.length
    dense_reach = export_mod.solidify(dense, 20_000).length - dense.length
    assert sparse_reach > dense_reach > 0


def test_glyph_size_is_capped_for_a_single_point():
    """One point does not produce a sphere that swallows the scene."""
    single = pv.PolyData(np.array([[1.0, 2.0, 3.0]]))
    out = export_mod.solidify(single, 20_000)
    assert out.n_faces > 0
    assert np.isfinite(out.length)


def test_large_images_are_strided_to_the_budget(tmp_path):
    """A structured dataset is thinned on its lattice rather than decimated."""
    image = pv.ImageData(dimensions=(400, 400, 1))
    image['height'] = np.arange(image.n_points, dtype=float)
    image.save(tmp_path / 'in.vti')
    out = tmp_path / 'out.ply'
    export_mod.export(str(tmp_path / 'in.vti'), str(out), 10_000, 20_000)
    scene = pv.read(out)
    assert scene.n_points == 100 * 100
    assert np.unique(scene.points[:, 0]).size == 100
    assert 'RGB' in scene.point_data


def test_volumes_with_scalars_are_cut_into_slices(tmp_path):
    """A volume with scalars is shown as three slices through its centre, coloured."""
    volume = pv.ImageData(dimensions=(30, 30, 30))
    volume['t'] = np.arange(volume.n_points, dtype=float)
    volume.save(tmp_path / 'in.vti')
    out = tmp_path / 'out.ply'
    export_mod.export(str(tmp_path / 'in.vti'), str(out), 2_000_000, 20_000)
    scene = pv.read(out)
    assert scene.n_points == 3 * 30 * 30
    assert 'RGB' in scene.point_data


def test_volume_cell_data_is_drawn_flat_on_the_slices(tmp_path):
    """Cell data on a volume reaches the slices and is drawn one colour per cell."""
    volume = pv.ImageData(dimensions=(30, 30, 30))
    volume.cell_data['c'] = np.arange(volume.n_cells, dtype=float)
    volume.save(tmp_path / 'in.vti')
    out = tmp_path / 'out.ply'
    export_mod.export(str(tmp_path / 'in.vti'), str(out), 2_000_000, 20_000)
    scene = pv.read(out)
    assert scene.n_points > 3 * 30 * 30
    assert 'RGB' in scene.point_data


def write_nrrd(path, volume):
    """Write a raw-encoded NRRD of a volume's scalars."""
    sizes = ' '.join(str(n) for n in volume.dimensions)
    header = (
        f'NRRD0004\ntype: float\ndimension: 3\nsizes: {sizes}\nencoding: raw\nendian: little\n\n'
    )
    path.write_bytes(header.encode() + np.asarray(volume['t'], dtype=np.float32).tobytes())


def write_metaimage(path, volume):
    """Write a volume's scalars as a MetaImage with the data in the same file."""
    size = ' '.join(str(n) for n in volume.dimensions)
    header = f'ObjectType = Image\nNDims = 3\nDimSize = {size}\nElementType = MET_FLOAT\n'
    header += 'ElementDataFile = LOCAL\n'
    path.write_bytes(header.encode() + np.asarray(volume['t'], dtype=np.float32).tobytes())


@pytest.mark.parametrize(
    ('ext', 'write'),
    [
        ('.nii', lambda path, volume: volume.save(path)),
        ('.mha', write_metaimage),
        ('.nrrd', write_nrrd),
    ],
)
def test_medical_volumes_are_cut_into_slices(tmp_path, ext, write):
    """A medical volume is read, sliced through its centre, and coloured by its values."""
    volume = pv.ImageData(dimensions=(20, 20, 20))
    volume['t'] = np.arange(volume.n_points, dtype=float)
    write(tmp_path / f'volume{ext}', volume)
    out = tmp_path / 'out.ply'
    export_mod.export(str(tmp_path / f'volume{ext}'), str(out), 2_000_000, 20_000)
    scene = pv.read(out)
    assert scene.n_points == 3 * 20 * 20
    assert 'RGB' in scene.point_data


def test_volume_skin_is_kept_whole_when_it_fits(tmp_path):
    """A volume with nothing to colour shows its outer surface, whole while it fits."""
    volume = pv.ImageData(dimensions=(60, 60, 60))
    volume.save(tmp_path / 'in.vti')
    out = tmp_path / 'out.ply'
    export_mod.export(str(tmp_path / 'in.vti'), str(out), 100_000, 20_000)
    # Six faces of 60 x 60 points; striding the volume itself would leave ~5 000.
    assert 20_000 <= pv.read(out).n_points <= 6 * 60 * 60
    export_mod.export(str(tmp_path / 'in.vti'), str(out), 5_000, 20_000)
    assert pv.read(out).n_points <= 5_000


def test_partitioned_datasets_are_drawn_as_one_surface(tmp_path):
    """The partitions of a .vtpd or VTKHDF file are combined, as blocks are."""
    pv.PartitionedDataSet([pv.Sphere(), pv.Cube()]).save(tmp_path / 'in.vtpd')
    out = tmp_path / 'out.ply'
    export_mod.export(str(tmp_path / 'in.vtpd'), str(out), 2_000_000, 20_000)
    assert pv.read(out).n_faces == pv.Sphere().n_faces + 12


@pytest.mark.needs_rendering
def test_step_models_are_drawn(tmp_path):
    """A STEP model is tessellated by pyvista-cad, read back as glTF, and drawn."""
    out = tmp_path / 'out.ply'
    export_mod.export(str(cad_examples.bracket_step_path()), str(out), 2_000_000, 20_000)
    assert pv.read(out).n_faces > 0


def test_dxf_drawings_are_drawn_as_tubes(tmp_path):
    """A DXF drawing holds only lines, which are given a surface."""
    out = tmp_path / 'out.ply'
    export_mod.export(str(cad_examples.drawing_dxf_path()), str(out), 2_000_000, 20_000)
    scene = pv.read(out)
    assert scene.n_faces > 0
    assert scene.n_lines == 0


def test_3mf_assemblies_are_drawn_as_one_surface(tmp_path):
    """The objects of a 3MF file are combined, as blocks are."""
    out = tmp_path / 'out.ply'
    export_mod.export(str(cad_examples.assembly_3mf_path()), str(out), 2_000_000, 20_000)
    assert pv.read(out).n_faces > 0


MESHIO_SURFACE_FORMATS = [
    '.avs',
    '.bdf',
    '.fem',
    '.mdpa',
    '.mesh',
    '.meshb',
    '.nas',
    '.off',
    '.tec',
    '.vol',
]


@pytest.mark.parametrize('ext', MESHIO_SURFACE_FORMATS)
def test_meshio_surface_formats_are_drawn(tmp_path, ext):
    """A surface written in a meshio format is read back through meshio and drawn."""
    source = tmp_path / f'mesh{ext}'
    pv.save_meshio(source, pv.Sphere().triangulate())
    out = tmp_path / 'out.ply'
    export_mod.export(str(source), str(out), 2_000_000, 20_000)
    assert pv.read(out).n_faces == pv.Sphere().n_faces


@pytest.mark.parametrize('ext', ['.pv', '.zvtk'])
@pytest.mark.filterwarnings('ignore::FutureWarning')
def test_zstandard_files_are_drawn_with_their_scalars(tmp_path, ext):
    """A Zstandard-compressed file written by pyvista-zstd is read back and coloured."""
    mesh = pv.Sphere()
    mesh['t'] = np.arange(mesh.n_points, dtype=float)
    mesh.save(tmp_path / f'mesh{ext}')
    out = tmp_path / 'out.ply'
    export_mod.export(str(tmp_path / f'mesh{ext}'), str(out), 2_000_000, 20_000)
    scene = pv.read(out)
    assert scene.n_faces == mesh.n_faces
    assert 'RGB' in scene.point_data


def test_flac3d_grids_are_drawn(tmp_path):
    """FLAC3D holds volume cells only, so their outer surface is drawn."""
    source = tmp_path / 'zones.f3grid'
    pv.save_meshio(source, pv.ImageData(dimensions=(4, 4, 4)).triangulate())
    out = tmp_path / 'out.ply'
    export_mod.export(str(source), str(out), 2_000_000, 20_000)
    assert pv.read(out).n_faces > 0


def test_binary_gmsh_files_are_drawn(tmp_path):
    """A binary Gmsh file, the form meshio reads reliably, is drawn."""
    source = tmp_path / 'mesh.msh'
    pv.save_meshio(source, pv.Sphere().triangulate(), file_format='gmsh', binary=True)
    out = tmp_path / 'out.ply'
    export_mod.export(str(source), str(out), 2_000_000, 20_000)
    assert pv.read(out).n_faces == pv.Sphere().n_faces


def readable_extensions() -> set[str]:
    """Return every extension ``pyvista.read`` accepts in this environment."""
    registered = {entry.extension for entry in reader_registry.registered_readers()}
    return set(readers.CLASS_READERS) | registered | set(meshio.extension_to_filetypes)


def test_format_table_accounts_for_every_readable_extension():
    """Each extension the environment reads is listed or deliberately unclaimed, and no other."""
    assert set(formats.FORMATS).isdisjoint(formats.UNCLAIMED)
    assert readable_extensions() == set(formats.FORMATS) | set(formats.UNCLAIMED)


def missing_reader(ext: str) -> str | None:
    """Return why the runtime cannot read an extension, or None when it can."""
    if ext not in readers.CLASS_READERS:
        registered = {entry.extension for entry in reader_registry.registered_readers()}
        registered |= set(meshio.extension_to_filetypes)
        return None if ext in registered else 'no reader is registered'
    try:
        readers.CLASS_READERS[ext](f'/nonexistent/sample{ext}')
    except ImportError as error:
        return str(error).splitlines()[0]
    except Exception:  # noqa: BLE001
        return None  # the reader exists and merely dislikes the path
    return None


@pytest.mark.needs_rendering
def test_every_default_extension_has_a_reader():
    """The installed environment can read every format that is claimed by default."""
    missing = {ext: why for ext in formats.default_extensions() if (why := missing_reader(ext))}
    assert missing == {}
