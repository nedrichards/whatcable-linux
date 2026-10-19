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
./scripts/local-flatpak.sh
flatpak run com.nedrichards.WhatCable.Devel
```

`run-tests` is enabled in the development manifest. A successful build proves
the Meson unit suite inside the manifest-pinned GNOME SDK. Host checks remain useful for quick
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

## Local Flatpak build storage

Use `./scripts/local-flatpak.sh` (defaults to development) for local checkout
builds and updates. Use `./scripts/local-flatpak.sh production` only when the
production manifest is intended. See `docs/local-flatpak.md`.
Use the normal manifests and keep their test gates enabled.

- Keep the durable update repository at `flatpak-repo/`. Never place it under
  `.flatpak-builder/` or another disposable build/cache directory.
- Use `.flatpak-builder/` for Builder state and `.flatpak-builder/staging` as
  the single staging location for both profiles. Build sequentially. Do not
  create per-task, per-validation or timestamped build/state/repository trees.
- Use `--delete-build-dirs` and clean module working directories and staging
  after success, failure and ordinary interruption, as the script does. Keep
  the reusable cache and downloads. Do not use `--keep-build-dirs` for routine
  automated builds. Debug retention needs an explicit task-specific reason
  and cleanup when finished.
- Do not run GNOME Builder or raw Builder commands concurrently with the
  script. Interactive GNOME Builder development remains supported via the
  `.Devel` manifest; prefer the script for automated validation and deployment.
- Keep directory-source `skip` lists excluding generated build directories,
  `target`, `.flatpak-builder*` and `flatpak-repo`, so artifacts are not copied
  into subsequent builds.
- Verify the installed app and its update origin after deployment. Never
  re-export an installed `export/` directory.

There is no enforced storage budget. Do not change Rust incremental/debug
settings as part of storage housekeeping without a separate request.
