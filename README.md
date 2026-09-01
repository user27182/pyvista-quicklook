# PyVista Quick Look

Press the space bar on a mesh file in the Finder and turn it with the mouse, the same
way macOS already previews `.ply` and `.usdz` models.

Selecting `flow.vtu` and pressing space shows its surface in the Quick Look panel,
coloured by the active scalars and free to rotate and zoom.

## Requirements

- macOS 12 or newer
- Xcode command line tools (`xcode-select --install`)

PyVista does not need to be installed; the installer provisions its own copy.

## Install

```bash
curl -LsSf https://raw.githubusercontent.com/user27182/pyvista-quicklook/main/scripts/bootstrap.sh | sh
```

Then select a `.vtu`, `.vtp`, or `.vtk` file in the Finder and press space.

The installer fetches [uv](https://docs.astral.sh/uv/) if it is missing, downloads the
source, creates a private environment holding PyVista and VTK, installs the `pvql`
helper, builds and registers `PyVistaQuickLook.app`, and loads PyVista once so the first
preview is quick. Nothing outside `~/Library/Application Support/PyVistaQuickLook`,
`~/Applications`, and `~/.local/bin` is touched, and no existing Python environment is
used or changed.

The first install downloads PyVista and VTK, about 600 MB.

From a checkout, the same script runs without downloading anything:

```bash
./scripts/install.sh                     # provisions its own PyVista
./scripts/install.sh --prefix /Applications
./scripts/install.sh --pyvista /path/to/venv/bin/pyvista   # use an existing one
```

Check the result with `pvql doctor`.

## Supported files

36 extensions are claimed by default, including `.vtk`, `.vti`, `.vtp`, `.vtu`, `.vtm`,
`.vtkhdf`, `.pvd`, `.case`, `.exo`, `.foam`, `.cgns`, `.segy`, and `.xdmf`.

```bash
pvql types        # what is claimed now
pvql types --all  # every format pvql knows about
```

Formats macOS already previews — `.stl`, `.obj`, `.ply`, `.png` — are deliberately not
claimed, so the built-in viewer keeps handling them. Claim them by adding them to the
config and reinstalling:

```json
{ "extensions": { "add": [".stl", ".obj"], "remove": [".pdb"] } }
```

## How it works

The app bundle contains a Quick Look extension that declares a uniform type identifier
for each claimed extension. When the Finder previews one of those files, the extension
hands it to a background render service, which reads it with PyVista, extracts the
surface, colours the vertices by the active scalars, and writes a PLY. The extension
shows that PLY in a SceneKit view, which is what makes the preview turnable.

Datasets with no surface to show fall back to a still image rendered by
`pyvista plot --off-screen --screenshot`, which keeps the scalar bar and axes that the
interactive view leaves out. Setting `"interactive": false` in the config always uses
that still image.

Both are cached under `~/Library/Caches/PyVistaQuickLook`, keyed by the file's path,
size, and modification time, so editing a file invalidates its preview. Later previews
of the same file come from the cache.

Every preview runs PyVista in a fresh process, and VTK is 600 MB of libraries, so the
first one after a restart is slow until macOS has those pages cached. The service loads
them in the background when it starts, which is at login and whenever it is reinstalled,
so that cost is paid before you press space. `pvql warmup` does the same on demand, and
`"warm_on_start": false` turns the automatic pass off.

Cell data is sampled onto the points before colouring. Surfaces are sent whole:
decimating them costs more time than the larger file does, so `max_scene_points` is a
safety valve for very large meshes rather than a routine step. Set it to `0` to never
decimate.

When a preview fails, the Quick Look panel shows the error text instead.

### The render service

macOS runs Quick Look extensions in a sandbox that VTK cannot render inside, so
rendering happens in a launch agent instead. `scripts/install.sh` sets it up.

```bash
pvql service            # report whether it is loaded
pvql service --install  # (re)install and start it
pvql service --uninstall
```

Its output goes to `~/Library/Logs/pvqld.log`.

### Files in the Desktop, Documents, and Downloads folders

macOS keeps those folders private to each program, and the render service cannot read
them. The Quick Look extension copies the file it was asked to preview into its own
container so that the service can render it anyway.

A dataset that points at neighbouring files — `.pvd`, `.vtm`, `.case`, `.foam` — needs
those neighbours, which the copy does not include. Keep such datasets outside those
three folders, or grant the render service Full Disk Access in System Settings under
Privacy & Security.

## Configuration

`~/Library/Application Support/PyVistaQuickLook/config.json`

| Key | Default | Effect |
| --- | --- | --- |
| `pyvista` | discovered | Absolute path to the `pyvista` executable |
| `pvql` | discovered | Absolute path to the `pvql` helper |
| `interactive` | `true` | Show a turnable surface instead of a still image |
| `max_scene_points` | `2000000` | Decimate only above this many points; `0` never does |
| `colormap` | `'viridis'` | Colormap used to colour the surface |
| `warm_on_start` | `true` | Load PyVista and VTK when the render service starts |
| `window_size` | `[1024, 1024]` | Rendered preview size in pixels |
| `timeout` | `60` | Seconds before a render is abandoned |
| `max_file_size_mb` | `512` | Files above this size show a notice instead of a render |
| `background` | `null` | Background color passed to `pyvista plot` |
| `extra_args` | `[]` | Extra arguments appended to `pyvista plot` |
| `cache` | `true` | Reuse previously rendered previews |
| `log` | `false` | Append render activity to `pvql.log` beside the config file |

Changing `extensions` requires a reinstall, because the claimed types are baked into the
app bundle. Every other key takes effect on the next preview.

## Commands

```bash
pvql preview FILE     # render and print the path of the cached PNG
pvql warmup           # load PyVista and VTK ahead of the first preview
pvql warm DIR         # render a directory ahead of time
pvql types            # list claimed extensions
pvql doctor           # check every part of the integration
pvql service          # manage the render service
pvql config --init    # write a config file with discovered defaults
pvql cache --clear    # delete cached previews
```

## Troubleshooting

Run `pvql doctor` first; it checks the helper, the app, the extension registration, the
service, and a real render.

- **The panel says the service is not answering.** Run `pvql service --install`.
- **Nothing happens on space bar.** Confirm the type is claimed with `pvql types`, then
  check that Finder resolves it: `mdls -name kMDItemContentType yourfile.vtu` should
  report an `io.github.user27182.pyvista-quicklook.*` type.
- **Previews are stale.** `pvql cache --clear`.
- **A render fails.** Set `"log": true` in the config; activity is appended to
  `pvql.log` beside it. The extension's own log is in
  `~/Library/Containers/io.github.user27182.PyVistaQuickLook.QuickLook/Data/tmp/`.

## Development

```bash
uv sync --group dev
uv run pytest tests/          # helper tests, with coverage
uv run pre-commit run --all-files
./scripts/build.sh            # compile and sign the app bundle
```

`main` is protected by a pre-commit hook, so work on a branch.

Releases are published to PyPI by CI through trusted publishing: push a `v*` tag and
the `publish` job uploads from the `release` environment. That requires a matching
pending publisher configured on PyPI for this repository and workflow.

## Uninstall

```bash
./scripts/uninstall.sh
uv tool uninstall pyvista-quicklook
```

That removes the app, the private PyVista environment, the downloaded source, and the
cache, leaving only the config file.
