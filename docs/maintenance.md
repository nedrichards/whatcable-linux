# Maintenance and release checks

Dependency updates are proposed weekly by Dependabot for GitHub Actions and applicable language manifests. The Dependency health workflow runs weekly and on demand: it reports GNOME runtime/SDK and Rust SDK extension end-of-life, unavailable runtime refs, and outdated bundled sources via Flatpak External Data Checker. Pull requests validate dependency-checker coverage without blocking source changes on already-known update reports. Reports appear in the Actions summary and remain downloadable for 14 days. A network/checker failure is a failed check, not evidence that dependencies are current. Dependency reports suggest changes; they never repin a stable application source or publish releases.

The required source and Flatpak jobs retain the repository's application-specific tests. Development artifacts have a separate .Devel identity, a checkout SHA, a 14-day lifetime, and an installation command in the summary. SDK/build success does not establish hardware, live-service, portal, compositor, or multi-monitor behaviour; keep the existing manual and installed-app gates in the release process.

## Releases

Dispatch `Publish Release Flatpaks` from the default branch with an existing `vX.Y.Z` tag. The tag must be an ancestor of that checkout. The workflow uses `build-aux/stable/com.nedrichards.WhatCable.json` and verifies its source. A pinned production manifest must match the tag exactly; a local-source manifest is read from the tag and converted to an exact Git commit in a temporary build manifest. Both x86_64 and aarch64 builds must pass before publication, with SHA256SUMS. Existing releases are never overwritten.

GitHub bundles are sideloadable packages. Flathub updates continue through the Flathub repository review process. This workflow does not submit to or publish on Flathub.

The temporary release build includes the development manifest's cleanup-only pytest module. It runs the tagged production source tests and removes test tooling from the final bundle. The committed stable source pin remains unchanged.

GitHub repository settings also enable dependency vulnerability alerts, Dependabot security updates, and weekly CodeQL default setup. Security updates propose pull requests; they do not merge them or publish app releases. The default CodeQL configuration lives in GitHub settings, alongside these versioned maintenance workflows.
