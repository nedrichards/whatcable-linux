"""Check runtime support and prepare bundled sources for External Data Checker."""

import argparse
import configparser
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

FLATPAK = shutil.which("flatpak") or "/usr/bin/flatpak"


def modules(items, parent):
    for item in items:
        if isinstance(item, str):
            # Cargo is covered by Dependabot/RustSec, not URL probing every crate.
            if "cargo-sources" not in item:
                path = parent / item
                yield from modules(json.loads(path.read_text()), path.parent)
        else:
            yield item
            yield from modules(item.get("modules", []), parent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    failed = False
    seen = set()
    external = []
    for filename in args.manifests:
        path = Path(filename)
        manifest = json.loads(path.read_text())
        for runtime in (manifest["runtime"], manifest["sdk"]):
            ref = f"{runtime}//{manifest['runtime-version']}"
            if ref in seen:
                continue
            seen.add(ref)
            if not args.prepare_only:
                result = subprocess.run(  # noqa: S603 -- fixed Flatpak command, no shell
                    [FLATPAK, "remote-info", "--user", "flathub", ref],
                    env={**os.environ, "LC_ALL": "C"},
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=120,
                    check=False,
                )
                print(f"## {filename}: {ref}\n\n```text\n{result.stdout}\n```")
                if result.returncode or re.search(r"end.of.life|no longer supported", result.stdout, re.IGNORECASE):
                    print(f"::error::Runtime check failed or reached end-of-life: {ref}")
                    failed = True
        if manifest.get("sdk-extensions") and not args.prepare_only:
            metadata = subprocess.run(  # noqa: S603 -- fixed Flatpak command, no shell
                [
                    FLATPAK,
                    "remote-info",
                    "--user",
                    "--show-metadata",
                    "flathub",
                    f"{manifest['sdk']}//{manifest['runtime-version']}",
                ],
                text=True,
                capture_output=True,
                timeout=120,
                check=False,
            )
            try:
                if metadata.returncode:
                    raise ValueError(metadata.stderr)
                config = configparser.ConfigParser(interpolation=None)
                config.read_string(metadata.stdout)
                for extension in manifest["sdk-extensions"]:
                    if "//" in extension:
                        ref = extension
                    else:
                        sections = [
                            section
                            for section in config.sections()
                            if section.startswith("Extension ")
                            and extension.startswith(section.removeprefix("Extension "))
                        ]
                        if not sections:
                            raise ValueError(f"No SDK extension branch metadata for {extension}")
                        section = max(sections, key=len)
                        branch = config[section].get("version")
                        if not branch:
                            raise ValueError(f"No SDK extension version for {extension}")
                        ref = f"{extension}//{branch}"
                    if ref in seen:
                        continue
                    seen.add(ref)
                    result = subprocess.run(  # noqa: S603 -- fixed Flatpak command, no shell
                        [FLATPAK, "remote-info", "--user", "flathub", ref],
                        env={**os.environ, "LC_ALL": "C"},
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        timeout=120,
                        check=False,
                    )
                    print(f"## {filename}: {ref}\n\n```text\n{result.stdout}\n```")
                    if result.returncode or re.search(r"end.of.life|no longer supported", result.stdout, re.IGNORECASE):
                        print(f"::error::SDK extension check failed or reached end-of-life: {ref}")
                        failed = True
            except (ValueError, configparser.Error) as error:
                print(f"::error::Cannot determine supported SDK extension refs: {error}")
                failed = True
        for module in modules(manifest["modules"], path.parent):
            sources = [
                s
                for s in module.get("sources", [])
                if isinstance(s, dict) and s.get("type") in ("archive", "file", "git") and s.get("x-checker-data")
            ]
            if sources:
                external.append(
                    {
                        "name": f"dependency-{len(external)}",
                        "buildsystem": "simple",
                        "build-commands": [],
                        "sources": sources,
                    }
                )
            for source in module.get("sources", []):
                if (
                    isinstance(source, dict)
                    and source.get("url")
                    and "x-checker-data" not in source
                    and source.get("type") != "git"
                ):
                    print(f"::error::No upstream version checker for {module['name']}: {source['url']}")
                    failed = True
    # This input deliberately contains dependencies only, never the app's release pin.
    manifest["modules"] = external
    Path("dependency-sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {len(external)} bundled dependency groups for upstream version checks.")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
