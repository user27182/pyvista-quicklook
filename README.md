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

Then select a `.vtu`, `.vtp`, or `.vtk` file in the Finder and press space.

The installer downloads the latest release, fetches [uv](https://docs.astral.sh/uv/)
if it is missing, creates a private environment holding PyVista, installs the `pvql`
helper, registers `PyVistaQuickLook.app`, starts the render service, and loads PyVista
once so the first preview is quick. Nothing outside
`~/Library/Application Support/PyVistaQuickLook`, `~/Applications`, and `~/.local/bin`
is touched, and no existing Python environment is used or changed.

Check the result with `pvql doctor`.

From a checkout, `./scripts/install.sh` does the same and builds the app from source,
which needs the Xcode command line tools (`xcode-select --install`):

```bash
./scripts/install.sh --prefix /Applications                # install for all users
./scripts/install.sh --pyvista /path/to/venv/bin/pyvista   # use an existing PyVista
./scripts/install.sh --app /path/to/PyVistaQuickLook.app   # skip the build
```

### What gets installed

About 150 MB, in `~/Library/Application Support/PyVistaQuickLook/venv`:

- PyVista, from git until 0.49 is released, installed with `--no-deps`
- [cvista](https://github.com/pyvista/cvista)`[io]`, the reading half of a VTK fork,
  in place of stock VTK
- numpy, pooch, scooby, typing-extensions

Point `--pyvista` at an environment you already have to use that instead. It needs
PyVista 0.49 or newer.

## Supported files

Most VTK, ParaView, and simulation formats are claimed by default: `.vtk`, `.vti`,
`.vtp`, `.vtu`, `.vtm`, `.vtkhdf`, `.pvd`, `.case`, `.exo`, `.foam`, `.cgns`, `.segy`,
`.xdmf`, and more.

```bash
pvql types        # what is claimed now
pvql types --all  # every format pvql knows about
```

Formats macOS already previews — `.stl`, `.obj`, `.ply`, `.png` — are deliberately not
claimed, so the built-in viewer keeps handling them. Claim them by adding them to the
config and reinstalling:

```json
{ "extensions": { "add": [".stl", ".obj"], "remove": [".segy"] } }
```

## How it works

The app bundle contains a Quick Look extension that declares a uniform type identifier
for each claimed extension. When the Finder previews one of those files, the extension
hands it to a background render service, which reads it with PyVista, extracts the
surface, colours the vertices by the active scalars, and writes a PLY. The extension
shows that PLY in a SceneKit view, which is what makes the preview turnable.

Point data is interpolated across each face. Cell data is drawn flat: the cells are
split apart first, so each keeps its own colour. Lines are drawn as tubes and point
clouds as spheres, sized to the spacing between points.

Previews are cached under `~/Library/Caches/PyVistaQuickLook`, keyed by the file's
path, size, and modification time, so editing a file invalidates its preview.

The service loads PyVista and VTK in the background when it starts, which is at login
and whenever it is reinstalled, so the first preview does not wait for them. `pvql
warmup` does the same on demand, and `"warm_on_start": false` turns the automatic pass
off.

Surfaces are sent whole up to `max_scene_points`. Above that, images and volumes are
thinned on their lattice and other surfaces are decimated. Set it to `0` to never
thin.

When a preview fails, the Quick Look panel shows the error text instead.

### Still images

An environment with the full PyVista, named with `--pyvista`, can also render still
images with `pyvista plot --off-screen --screenshot`, which keep the scalar bar and axes
the interactive view leaves out. They are used when a dataset has no surface to show,
or always when `"interactive"` is `false`. The default environment has no rendering
modules and shows the error instead.

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
| `pyvista` | unset | `pyvista` executable of an environment that can render still images |
| `pvql` | discovered | Absolute path to the `pvql` helper |
| `interactive` | `true` | Show a turnable surface; `false` always uses a still image |
| `max_scene_points` | `2000000` | Thin surfaces above this many points; `0` never does |
| `max_glyph_points` | `20000` | Draw at most this many points of a point cloud; `0` draws all |
| `max_file_size_mb` | `512` | Files above this size show a notice instead of a preview |
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
