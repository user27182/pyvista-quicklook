# PyVista Quick Look

Press the space bar on a mesh file in the Finder and turn it with the mouse, the same
way macOS already previews `.ply` and `.usdz` models.

Selecting `flow.vtu` and pressing space shows its surface in the Quick Look panel,
coloured by the active scalars and free to rotate and zoom.

## Install

macOS 12 or newer. Nothing else needs to be installed first.

```bash
curl -LsSf https://raw.githubusercontent.com/user27182/pyvista-quicklook/main/scripts/bootstrap.sh | sh
```

Then select a `.vtu`, `.vtp`, or `.vtk` file in the Finder and press space. Check the
result with `pvql doctor`.

### What the installer does

1. Downloads the latest release: the installer scripts, about 1 MB, and the prebuilt
   app, about 200 KB.
2. Installs [uv](https://docs.astral.sh/uv/) if it is missing, and a Python 3.12 if uv
   finds none on the machine.
3. Installs the `pvql` helper as a uv tool.
4. Creates a private Python environment and installs
   [PyVista](https://github.com/pyvista/pyvista) with its io extras, among them
   [meshio](https://github.com/nschloe/meshio) and, from PyVista 0.49,
   [pyvista-frd-reader](https://github.com/pyvista/pyvista-frd-reader), along with
   [cvista](https://github.com/pyvista/cvista) and
   [pyvista-cad](https://github.com/pyvista/pyvista-cad). This is the step that takes a
   while: about 400 MB of wheels.
5. Writes the configuration file and loads PyVista once, so the first preview is quick.
6. Copies the app from the download into `~/Applications`, registers it with Launch
   Services and Quick Look, and removes the downloaded copy.
7. Installs the render service as a launch agent. It appears as PyVista Quick Look
   under Login Items in System Settings.

No system Python and no existing environment is used or changed.

### Where things go

| Path | What | Size |
| --- | --- | --- |
| `~/Library/Application Support/PyVistaQuickLook/venv` | The PyVista environment | 380 MB |
| `~/Library/Application Support/PyVistaQuickLook/config.json` | Configuration | 4 KB |
| `~/Library/Application Support/PyVistaQuickLook/src` | The installer scripts, kept for `uninstall.sh` | 1 MB |
| `~/Applications/PyVistaQuickLook.app` | The app and its Quick Look extension | 500 KB |
| `~/Library/Application Support/uv/tools/pyvista-quicklook` | The `pvql` helper | 400 KB |
| `~/.local/bin/pvql`, `~/.local/bin/pyvista-quicklook` | Links to the helper | |
| `~/Library/LaunchAgents/io.github.user27182.pvqld.plist` | The render service | 4 KB |
| `~/Library/Logs/pvqld.log` | The service's output | grows slowly |
| `~/Library/Containers/io.github.user27182.PyVistaQuickLook.QuickLook` | The extension's sandbox: its log and staged copies | small |
| `~/Library/Caches/PyVistaQuickLook` | One built preview per file previewed | grows with use |
| `~/.local/bin/uv`, `~/Library/Application Support/uv` | uv, and Python 3.12 if uv had to fetch one | 45 MB, plus Python |
| `~/.cache/uv` | uv's download cache; the environment's files are clones of it, not copies | shared |

About 385 MB in total, or 430 MB when uv is installed too. The environment is the bulk
of it:

- [cvista](https://github.com/pyvista/cvista)`[all]`, a VTK fork used in place of
  stock VTK, 137 MB
- cascadio, [pyvista-cad](https://github.com/pyvista/pyvista-cad)'s STEP reader, 69 MB
- matplotlib, 28 MB
- numpy, 25 MB
- ezdxf, pyvista-cad's DXF reader, 20 MB
- PyVista, from git until 0.49 is released, [meshio](https://github.com/nschloe/meshio),
  and the remaining dependencies, about 100 MB

`pvql cache --clear` empties the preview cache. `scripts/uninstall.sh` removes
everything above except the configuration file and uv.

From a checkout, `./scripts/install.sh` does the same and builds the app from source,
which needs the Xcode command line tools (`xcode-select --install`):

```bash
./scripts/install.sh --prefix /Applications                # install for all users
./scripts/install.sh --app /path/to/PyVistaQuickLook.app   # skip the build
```

## Supported files

76 extensions are claimed, so pressing space on any of these files opens
this preview. A file that turns out not to be a mesh, such as a `.dat` holding a table
of numbers, is shown as plain text instead, the way Quick Look would have shown it.

| Format | Extensions | Format | Extensions |
| --- | --- | --- | --- |
| 3D Studio Model | `.3ds` | OpenFOAM Case | `.foam` |
| 3MF Model | `.3mf` | ParaView Data Collection | `.pvd` |
| AVS UCD Data | `.inp` | PERMAS Data | `.dato`, `.post` |
| AVS UCD Mesh | `.avs` | PLOT3D Metadata | `.p3d` |
| Binary Marching Cubes Surface | `.tri` | Point Cloud | `.pts` |
| BYU Geometry | `.g` | ProStar Mesh | `.vrt` |
| CalculiX Result | `.frd` | Protein Data Bank | `.pdb` |
| CGNS Data | `.cgns` | PyVista Zstandard Data | `.pv`, `.zvtk` |
| Digital Elevation Model | `.dem` | SEG-Y Seismic Data | `.segy`, `.sgy` |
| DXF Drawing | `.dxf` | SLC Volume | `.slc` |
| Eclipse GRDECL Grid | `.grdecl` | STEP Model | `.step`, `.stp` |
| EnSight Case | `.case` | Tecplot ASCII Data | `.tec` |
| Exodus II Data | `.e`, `.ex2`, `.exii`, `.exo` | Tecplot Data | `.dat` |
| Facet Surface | `.facet` | TetGen Mesh | `.ele`, `.node` |
| FLAC3D Grid | `.f3grid` | VRML Model | `.vrml`, `.wrl` |
| Fluent Case | `.cas` | VTK File Series | `.series` |
| GAMBIT Neutral Mesh | `.neu` | VTK HDF | `.vtkhdf` |
| Gaussian Cube | `.cube` | VTK Image Data | `.vti` |
| GE Signa MR Image | `.mr` | VTK Legacy Data | `.vtk` |
| Gmsh Mesh | `.msh` | VTK MultiBlock | `.vtm`, `.vtmb` |
| Kratos Model Part | `.mdpa` | VTK Parallel Image Data | `.pvti` |
| Medit Mesh | `.mesh`, `.meshb` | VTK Parallel Legacy Data | `.pvtk` |
| MetaImage Volume | `.mha`, `.mhd` | VTK Parallel Rectilinear Grid | `.pvtr` |
| MFIX Result | `.res` | VTK Parallel Unstructured Grid | `.pvtu` |
| MINC Volume | `.mnc` | VTK Partitioned Dataset | `.vtpd` |
| Nastran Bulk Data | `.bdf`, `.fem`, `.nas` | VTK PolyData | `.vtp` |
| Nek5000 Data | `.nek5000` | VTK Rectilinear Grid | `.vtr` |
| Netgen Mesh | `.vol` | VTK Structured Grid | `.vts` |
| NIfTI Volume | `.nii` | VTK Unstructured Grid | `.vtu` |
| NRRD Volume | `.nhdr`, `.nrrd` | XDMF Data | `.xdmf` |
| Object File Format Mesh | `.off` | | |

PyVista can also read these, which are not claimed:

- macOS previews it: `.bmp`, `.dcm`, `.gif`, `.glb`, `.gltf`, `.hdr`, `.jpeg`, `.jpg`, `.obj`, `.ply`, `.png`, `.pnm`, `.stl`, `.tif`, `.tiff`
- disk images own the extension: `.img`
- camera raw images own the extension: `.raw`
- XML owns the extension: `.xml`
- the Finder sees .gz: `.dato.gz`, `.nii.gz`, `.post.gz`, `.vol.gz`
- needs an OpenCascade kernel: `.brep`, `.brp`, `.fcstd`, `.iges`, `.igs`
- needs ifcopenshell: `.ifc`
- needs the openscad program: `.scad`
- a general HDF5 container: `.h5`, `.hdf`
- needs h5py: `.h5m`, `.hmf`, `.med`, `.xmf`
- meshio fails to read it: `.su2`, `.ugrid`
- meshio hangs on it: `.wkt`
- meshio writes it but does not read it: `.svg`

Claims on the extensions macOS previews itself, such as STL and PLY, or that another kind
of file owns, are ignored by macOS, which is why those are not claimed. To claim fewer,
or to add one of the others, edit the config and run the install command again, which
rebuilds the app with the new claims:

```json
{ "extensions": { "add": [".h5"], "remove": [".dat"] } }
```

## How it works

The app bundle contains a Quick Look extension that declares a uniform type identifier
for each claimed extension. When the Finder previews one of those files, the extension
hands it to a background render service, which reads it with PyVista, extracts the
surface, colours the vertices by the active scalars, and writes a PLY. The extension
shows that PLY in a SceneKit view, which is what makes the preview turnable.

Point data is interpolated across each face. Cell data is drawn flat: the cells are
split apart first, so each keeps its own colour. Lines are drawn as tubes and point
clouds as spheres, sized to the spacing between points. A volume that carries scalars
is cut into three slices through its centre; one without is shown as its outer surface.

Previews are cached under `~/Library/Caches/PyVistaQuickLook`, keyed by the file's
path, size, and modification time, so editing a file invalidates its preview.

The service loads PyVista and VTK in the background when it starts, which is at login
and whenever it is reinstalled, so the first preview does not wait for them. `pvql
warmup` does the same on demand, and `"warm_on_start": false` turns the automatic pass
off.

Surfaces are sent whole up to `max_scene_points`. Above that, images and volumes are
thinned on their lattice and other surfaces are decimated. Set it to `0` to never
thin.

A claimed file that turns out not to be a mesh, such as a `.dat` holding a table of
numbers or a `.g` holding G-code, is shown as plain text, the way Quick Look would have
shown it. When a preview fails for another reason, the panel shows the error text.

### Still images

With `"interactive": false` in the config, every preview is a still image rendered by
`pyvista plot --off-screen --screenshot` instead, which keeps the scalar bar and axes
the interactive view leaves out.

### The render service

macOS runs Quick Look extensions in a sandbox that VTK cannot run inside, so reading
and conversion happen in a launch agent instead. The installer sets it up.

```bash
pvql service            # report whether it is loaded
pvql service --install  # (re)install and start it
pvql service --uninstall
```

It appears as PyVista Quick Look under Login Items in System Settings, and its output
goes to `~/Library/Logs/pvqld.log`.

### Files in the Desktop, Documents, and Downloads folders

macOS keeps those folders private to each program, and the render service cannot read
them. The Quick Look extension copies the file it was asked to preview into its own
container so that the service can convert it anyway.

A dataset that points at neighbouring files — `.pvd`, `.vtm`, `.case`, `.foam` — needs
those neighbours, which the copy does not include. Keep such datasets outside those
three folders, or grant the render service Full Disk Access in System Settings under
Privacy & Security.

## Configuration

`~/Library/Application Support/PyVistaQuickLook/config.json`

| Key | Default | Effect |
| --- | --- | --- |
| `python` | set at install | Interpreter of the PyVista environment |
| `pvql` | discovered | Absolute path to the `pvql` helper |
| `interactive` | `true` | Show a turnable surface; `false` renders a still image instead |
| `max_scene_points` | `2000000` | Thin surfaces above this many points; `0` never does |
| `max_glyph_points` | `20000` | Draw at most this many points of a point cloud; `0` draws all |
| `max_file_size_mb` | `512` | Files above this size show a notice instead of a preview, and are never copied |
| `timeout` | `60` | Seconds before a conversion is abandoned |
| `warm_on_start` | `true` | Load PyVista and VTK when the render service starts |
| `window_size` | `[1024, 1024]` | Still image size in pixels |
| `background` | `null` | Background colour passed to `pyvista plot` |
| `extra_args` | `[]` | Extra arguments appended to `pyvista plot` |
| `cache` | `true` | Reuse previously built previews |
| `log` | `false` | Append activity to `pvql.log` beside the config file |

Changing `extensions` requires a reinstall, because the claimed types are baked into the
app bundle. Every other key takes effect on the next preview.

## Commands

```bash
pvql preview FILE     # build a preview and print its cached path
pvql warm DIR         # build previews for a directory ahead of time
pvql warmup           # load PyVista and VTK ahead of the first preview
pvql types            # list claimed extensions
pvql doctor           # check every part of the integration
pvql service          # manage the render service
pvql config --init    # write a config file with discovered defaults
pvql cache --clear    # delete cached previews
```

## Troubleshooting

Run `pvql doctor` first; it checks the helper, the app, the extension registration, the
service, and a real preview.

- **The panel says the service is not answering.** Run `pvql service --install`.
- **Nothing happens on space bar.** Confirm the type is claimed with `pvql types`, then
  check that Finder resolves it: `mdls -name kMDItemContentType yourfile.vtu` should
  report an `io.github.user27182.pyvista-quicklook.*` type.
- **Previews are stale.** `pvql cache --clear`.
- **A preview fails.** Set `"log": true` in the config; activity is appended to
  `pvql.log` beside it. The extension's own log is in
  `~/Library/Containers/io.github.user27182.PyVistaQuickLook.QuickLook/Data/tmp/`.

## Development

```bash
uv sync --group dev
uv run pytest tests/          # helper and exporter tests, with coverage
uv run pre-commit run --all-files
./scripts/build.sh            # compile and sign the app bundle
```

`.python-version` pins the interpreter to 3.12, the last release cvista ships rendering
wheels for, and `[tool.uv]` in `pyproject.toml` overrides PyVista's stock VTK requirement
so the test environment holds the same packages the installer provisions.

PyVista is pinned to one commit, in `pyproject.toml` and `scripts/install.sh` alike.
Bumping it reruns a test that compares every extension the environment can read with
the format table, so a reader that PyVista adds, drops, or moves to a plugin shows up as
a failure to resolve in `formats.py`. The README's format tables are generated from
PyVista's reader tables and checked by another test:

```bash
uv run python -m pyvista_quicklook._formats_table README.md
```

`main` is protected by a pre-commit hook, so work on a branch.

Releases are published by CI: push a `v*` tag and the `publish` job uploads the helper
to PyPI through trusted publishing from the `release` environment, while the `release`
job attaches the built app to the tag's GitHub release, which is what the installer
downloads.

## Uninstall

```bash
./scripts/uninstall.sh
uv tool uninstall pyvista-quicklook
```

That removes the app, the render service, the private PyVista environment, the
download, and the cache, leaving only the config file.
