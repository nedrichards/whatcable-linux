# Flathub readiness

Audit date: 5 September 2026. This is an upstream engineering checklist,
not submission text or a promise of acceptance.

## Audit results

- Development Flatpak built and installed successfully with the Meson unit suite,
  including refresh concurrency, unchanged-report, failure/retry, shutdown, and
  literal-label regression coverage.
- Ruff, whitespace checks, desktop validation, and AppStream validation passed.
  AppStream emitted only the informational uppercase application-ID notice.
- Both manifest lint checks and the screenshot-mirrored development payload lint
  passed. The pinned production release was not rebuilt or changed.
- Installed GTK window and literal hardware-label smoke test passed without
  markup warnings.
- Ten scans in the installed sandbox took 14.59–15.97 ms on this machine and
  returned eight USB devices, five advanced entries, and no kernel Type-C ports.
  These timings describe this hardware only, not a general performance guarantee.
- Removed the unnecessary Thunderbolt authorization-key read. Hardware scanning
  now runs off the GTK thread, concurrent refreshes coalesce, and unchanged
  reports no longer rebuild the widgets. Hardware text is treated literally.
- Physical Type-C/PD hotplug and the broader visual/accessibility matrix below
  remain unverified. Passing automated checks does not establish Flathub acceptance.

## Before release

- Validate the development Flatpak, its installed payload, desktop entry,
  AppStream metadata, and both manifests with the Flathub linter.
  For Flathub-style screenshot mirroring, build with
  `--compose-url-policy=full --mirror-screenshots-url=https://dl.flathub.org/media`.
  Ordinary local builds otherwise report `appstream-external-screenshot-url`.
- Manually exercise hotplug, refresh, raw data, keyboard navigation, light/dark
  appearance, scaling, and narrow windows. Confirm that unchanged polls preserve
  focus, text selection, scrolling, and expanded details.
- Test ordinary USB inspection without extra host permissions. Test missing
  Type-C data and inaccessible Chrome EC hardware. Verify optional EC readings
  on supported hardware separately; do not require an ACL change for basic use.
- Check the screenshot against the release UI and ensure its public URL works.
- Publish an explicitly approved release containing the fixes. Update the
  project version and AppStream release entry, then pin the stable manifest to
  that published tag and exact commit. The existing stable manifest still
  targets v0.1.0 and does not build local fixes.
- Build and lint that exact production release; development validation alone
  does not prove the older production payload.

## Submission decisions

- Review eligibility with Flathub: its current inclusion rules restrict host
  system utilities and applications needing complicated host setup. WhatCable
  offers a read-only graphical inspector, but reviewer acceptance is not assured.
- Explain why `--device=all` is needed for optional `/dev/cros_ec` inspection.
  The app has no network or home-directory permission, and opens the EC device
  read-only with a single permitted command. Device access does not override
  host permissions. Check reviewer expectations for this broad permission.
- Confirm control of `nedrichards.com` for `com.nedrichards.WhatCable` and
  complete domain verification after acceptance if desired.
- Review licensing and provenance, including the approximate extent of generated
  code, documentation, and packaging. Flathub requires disclosure of generated
  material and evaluates it at reviewer discretion.
- The maintainer must author and open the submission and handle review themselves:
  current policy prohibits AI-generated submission messages and review interactions.

Sources checked for this audit:

- https://docs.flathub.org/docs/for-app-authors/requirements
- https://docs.flathub.org/docs/for-app-authors/submission
- https://docs.flathub.org/docs/for-app-authors/metainfo-guidelines/quality-guidelines
- https://docs.flathub.org/docs/for-app-authors/verification

Listing quality guidelines improve presentation and promotion; they are distinct
from mandatory inclusion requirements. There is no requirement to eliminate every
possible performance issue, but visible failures and unreliable core functionality
must be resolved before submission.
