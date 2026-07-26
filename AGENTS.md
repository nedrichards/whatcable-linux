# Repository guidance

## Project map

- `src/whatcable_linux/` contains the Python application, sysfs readers, the
  Framework Chrome EC backend, and presentation helpers.
- `tests/` contains hardware-independent unit tests built from temporary sysfs
  fixtures.
- `data/` contains desktop integration, AppStream metadata, styling, the icon,
  and screenshots.
- `build-aux/com.nedrichards.WhatCable.Devel.json` is the authoritative local
  development and test Flatpak. It builds this checkout and runs the Meson test
  suite. Keep its desktop, AppStream, icon, and runtime application identities
  aligned under the `.Devel` ID.
- `build-aux/stable/com.nedrichards.WhatCable.json` is production packaging
  pinned to a published tag and commit. Change it only for an explicit release.

## Working conventions

- Read `README.md` before build, packaging, or runtime work. Inspect the working
  tree before editing and preserve unrelated user changes.
- Keep hardware access read-only. The Chrome EC backend must not grow a generic
  command interface; it is limited to `EC_CMD_USB_PD_POWER_INFO`.
- Treat missing, permission-denied, and disappearing sysfs devices as normal
  runtime states rather than fatal errors.
- Add a focused regression test for behavioural changes. Tests must not depend
  on the host exposing particular USB-C hardware.
- Do not edit or commit `_build/`, `build/`, Flatpak Builder output,
  `.flatpak-builder/`, local captures, agent state, or credentials.

## Build and validation

The development Flatpak is authoritative for GTK, SDK, packaging, and runtime
changes:

```sh
flatpak run org.flatpak.Builder --user --install --force-clean \
  --disable-rofiles-fuse build-flatpak-devel \
  build-aux/com.nedrichards.WhatCable.Devel.json
flatpak run com.nedrichards.WhatCable.Devel
```

`run-tests` is enabled in the development manifest. A successful build proves
the Meson unit suite inside GNOME SDK 50. Host checks remain useful for quick
iteration:

```sh
python3 -m pytest -q
ruff check src tests
meson setup build
meson test -C build --print-errorlogs
appstreamcli validate --pedantic --no-net \
  data/com.nedrichards.WhatCable.metainfo.xml
desktop-file-validate data/com.nedrichards.WhatCable.desktop
```

Reserve `build/` for host Meson and `_build/` for GNOME Builder or explicit
GNOME SDK commands. Never open Builder's `_build/` with host Meson. Use the
development manifest in GNOME Builder; do not select the stable manifest while
working on local source.

## Packaging and Git

- Do not repin the stable manifest, create a release, or tag a commit unless the
  user explicitly asks for a release.
- Review `git status` and the complete diff before staging. Use concise,
  behaviour-based commits and only commit, push, or publish when requested.
- Report the checks actually run and any hardware-dependent verification that
  remains.
