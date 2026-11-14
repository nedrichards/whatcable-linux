# Continuous integration

Actions use immutable action revisions, read-only repository permissions by
default, bounded jobs, cancellation of obsolete development runs, and grouped
Dependabot action updates. Workflow syntax and shell snippets are checked with
checksum-pinned actionlint on native x86_64 and aarch64 runners. Dependency repair
jobs retain their existing narrowly scoped write access and trusted generators.

Tested development artifacts are for review, with source provenance and checksums;
diagnostics are retained even when tests fail. Reports and captures must use
fixtures, never account credentials, personal data or hardware identifiers.
Where a release workflow is configured, it attests verified files and prepares
drafts for manual publication. Native Flatpak release packaging requires both targets. CI signing establishes
build provenance; it does not replace release signing or human acceptance.

Flatpak builds run on native x86_64 and aarch64 inside the digest-pinned official GNOME 51 Flathub container. The runner host does not install Flatpak. Existing source tests remain required; exported bundles are installed and exercised with app-specific checks. Fixture captures and reports are retained for review. Weekly builds check SDK compatibility; runtime and bundled-source health checks report upstream maintenance findings.

Workflow syntax and shell snippets are checked locally before publication. Hosted
execution provides the architecture and installed-artifact evidence; generated
captures still require human visual review. No release or tag is created by this
maintenance change.

Fixture capture waits for three stable native frame allocations and a renderable
node. Logs record requested and allocated widths; a widget minimum may prevent
the requested compact width. Captures provide review evidence, while the existing
regression suite remains the behavioral gate.
