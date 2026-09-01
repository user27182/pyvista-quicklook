# PyVista Quick Look

Press the space bar on a mesh file in the Finder and see it rendered, the same way
images and PDFs already preview.

Selecting `flow.vtu` and pressing space runs `pyvista plot` on it off-screen and shows
the result in the Quick Look panel.

## Requirements

- macOS 12 or newer
- Xcode command line tools (`xcode-select --install`)
- A Python environment with PyVista installed, providing the `pyvista` command

## Install

```bash
./scripts/install.sh --pyvista /path/to/your/venv/bin/pyvista
```

This installs the `pvql` helper, starts the render service, builds
`PyVistaQuickLook.app`, copies it to `~/Applications`, and registers it with Quick Look.
Pass `--prefix /Applications` to install for all users.

Check the result:

```bash
pvql doctor
```

Then select a `.vtu`, `.vtp`, or `.vtk` file in the Finder and press space.

## Supported files

36 extensions are claimed by default, including `.vtk`, `.vti`, `.vtp`, `.vtu`, `.vtm`,
`.vtkhdf`, `.pvd`, `.case`, `.exo`, `.foam`, `.cgns`, `.segy`, and `.xdmf`.

```bash
pvql types        # what is claimed now
pvql types --all  # every format pvql knows about
```

Formats macOS already previews — `.stl`, `.obj`, `.ply`, `.png` — are not claimed.
Claim them by adding them to the config and reinstalling:

```json
{ "extensions": { "add": [".stl", ".obj"], "remove": [".pdb"] } }
```

## How it works

The app bundle contains a Quick Look extension that declares a uniform type identifier
for each claimed extension. When the Finder previews one of those files, the extension
hands the file to a background render service, which runs
`pyvista plot --off-screen --screenshot` and caches the PNG under
`~/Library/Caches/PyVistaQuickLook`.

The first preview of a file takes a few seconds while PyVista starts up. Later previews
of the same file are served from the cache. Editing the file invalidates its cache entry.

When a render fails, the Quick Look panel shows the error text instead of an image.

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

## Tests

```bash
uv run --with pytest pytest tests/
```

## Uninstall

```bash
./scripts/uninstall.sh
uv tool uninstall pvql
```
