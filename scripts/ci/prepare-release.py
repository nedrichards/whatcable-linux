"""Verify a release tag and produce a build manifest without changing release pins."""

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

GIT = shutil.which("git") or "/usr/bin/git"


def git(*args):
    return subprocess.check_output(  # noqa: S603 -- Git argv, no shell
        [GIT, *args], text=True
    ).strip()


def prepare(manifest_path, tag, default_branch, workflow_ref, repository, test_manifest=None, c_release_tests=False):
    if workflow_ref != f"refs/heads/{default_branch}":
        raise ValueError("Dispatch releases from the default branch")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Expected an existing vX.Y.Z tag")
    commit = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    subprocess.run(  # noqa: S603 -- validated commit, no shell
        [GIT, "merge-base", "--is-ancestor", commit, "HEAD"], check=True
    )
    path = Path(manifest_path)
    manifest = json.loads(path.read_text())
    if manifest.get("app-id", manifest.get("id", "")).endswith(".Devel"):
        raise ValueError("Release manifest must use the production app ID")
    source = manifest["modules"][-1]["sources"][0]
    if source["type"] == "git":
        if source.get("commit") != commit or source.get("tag", tag) != tag:
            raise ValueError("Production source pin does not match the requested tag")
        checkout = git("rev-parse", "HEAD")
    elif source["type"] == "dir":
        # Read all manifest dependencies/configuration from the tagged release.
        manifest = json.loads(git("show", f"{commit}:{path.as_posix()}"))
        if manifest.get("app-id", manifest.get("id", "")).endswith(".Devel"):
            raise ValueError("Tagged manifest must use the production app ID")
        sources = manifest["modules"][-1]["sources"]
        if len(sources) != 1 or sources[0]["type"] != "dir":
            raise ValueError("Expected one local application source in the tag")
        sources[0] = {"type": "git", "url": f"https://github.com/{repository}.git", "commit": commit}
        checkout = commit
    else:
        raise ValueError("Unsupported application source")
    if test_manifest:
        development = json.loads(Path(test_manifest).read_text())
        if any(development[key] != manifest[key] for key in ("runtime", "runtime-version", "sdk")):
            raise ValueError("Test tools must target the production SDK")
        names = {module["name"] for module in manifest["modules"] if isinstance(module, dict)}
        tools = [
            module
            for module in development["modules"]
            if isinstance(module, dict) and module.get("cleanup") == ["*"] and module["name"] not in names
        ]
        if not tools:
            raise ValueError("Expected cleanup-only test tools in development manifest")
        manifest["modules"] = tools + manifest["modules"]
    if c_release_tests:
        application = manifest["modules"][-1]
        if application.get("buildsystem") != "meson":
            raise ValueError("C release test profile requires Meson")
        options = application.setdefault("build-options", {})
        options["cflags"] = options.get("cflags", "") + " -g0"
        application["test-rule"] = ""
        harness = Path(__file__).with_name("headless-meson.py").read_text()
        application["sources"].append({
            "type": "inline", "dest-filename": "ci-headless-meson.py", "contents": harness
        })
        application["test-commands"] = [
            "dbus-run-session -- python3 ../ci-headless-meson.py meson test --no-rebuild --print-errorlogs --timeout-multiplier=3 --num-processes=1"
        ]
    output = path.parent / "release-build.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"commit": commit, "checkout": checkout, "manifest": str(output), "version": tag[1:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--test-manifest", help="Development manifest providing cleanup-only test tools")
    parser.add_argument("--c-release-tests", action="store_true", help="Match the C CI size/test profile")
    args = parser.parse_args()
    result = prepare(
        args.manifest,
        os.environ["RELEASE_TAG"],
        os.environ["DEFAULT_BRANCH"],
        os.environ["WORKFLOW_REF"],
        os.environ["GITHUB_REPOSITORY"],
        args.test_manifest,
        args.c_release_tests,
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.writelines(f"{key}={value}\n" for key, value in result.items())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
