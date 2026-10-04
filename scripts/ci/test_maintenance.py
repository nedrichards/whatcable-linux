"""Regression coverage for maintenance reporting and release source safety."""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

GIT = shutil.which("git") or "/usr/bin/git"
HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


health = load("dependency-health")


class HealthTests(unittest.TestCase):
    def test_end_of_life_and_remote_failure_are_not_healthy(self):
        for status, output in [(0, "End-of-life: no longer supported"), (1, "Network unavailable")]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                before = Path.cwd()
                try:
                    os.chdir(tmp)
                    Path("app.json").write_text(
                        json.dumps(
                            {
                                "runtime": "org.gnome.Platform",
                                "sdk": "org.gnome.Sdk",
                                "runtime-version": "51",
                                "modules": [],
                            }
                        )
                    )
                    with (
                        patch("sys.argv", ["dependency-health.py", "app.json"]),
                        patch("subprocess.run", return_value=subprocess.CompletedProcess([], status, output)),
                    ):
                        self.assertEqual(health.main(), 1)
                finally:
                    os.chdir(before)


@unittest.skipUnless((HERE / "prepare-release.py").exists(), "No production release manifest")
class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.before = Path.cwd()
        os.chdir(self.tmp.name)
        self.release = load("prepare-release")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Release test")
        self.git("config", "user.email", "test@example.invalid")
        self.manifest = {
            "app-id": "com.example.App",
            "runtime": "org.gnome.Platform",
            "runtime-version": "51",
            "sdk": "org.gnome.Sdk",
            "modules": [{"name": "app", "sources": [{"type": "dir", "path": "."}]}],
        }
        self.write()
        self.git("add", "app.json")
        self.git("commit", "-qm", "Tagged source")
        self.git("tag", "v1.2.3")
        self.commit = self.git("rev-parse", "HEAD")

    def tearDown(self):
        os.chdir(self.before)
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(  # noqa: S603 -- temporary fixture repository, no shell
            [GIT, *args], text=True, stderr=subprocess.DEVNULL
        ).strip()

    def write(self):
        Path("app.json").write_text(json.dumps(self.manifest))

    def prepare(self, tag="v1.2.3", ref="refs/heads/main"):
        return self.release.prepare("app.json", tag, "main", ref, "owner/app")

    def test_local_release_reads_tag_not_current_dependency_configuration(self):
        self.manifest["runtime-version"] = "99"
        self.write()
        result = self.prepare()
        built = json.loads(Path("release-build.json").read_text())
        self.assertEqual(built["runtime-version"], "51")
        self.assertEqual(built["modules"][-1]["sources"][0]["commit"], self.commit)
        self.assertEqual(result["checkout"], self.commit)
        self.assertEqual(json.loads(Path("app.json").read_text())["runtime-version"], "99")

    def test_pinned_release_requires_exact_tag_commit(self):
        self.manifest["modules"][-1]["sources"][0] = {
            "type": "git",
            "url": "https://github.com/owner/app.git",
            "commit": "0" * 40,
        }
        self.write()
        with self.assertRaises(ValueError):
            self.prepare()
        self.manifest["modules"][-1]["sources"][0]["commit"] = self.commit
        self.write()
        self.assertEqual(self.prepare()["commit"], self.commit)

    def test_cleanup_only_tools_added_without_changing_production_pin(self):
        development = dict(self.manifest)
        development["modules"] = [{"name": "pytest", "cleanup": ["*"], "sources": []}]
        Path("development.json").write_text(json.dumps(development))
        self.release.prepare("app.json", "v1.2.3", "main", "refs/heads/main", "owner/app", "development.json")
        built = json.loads(Path("release-build.json").read_text())
        self.assertEqual(built["modules"][0]["name"], "pytest")
        self.assertEqual(built["modules"][0]["cleanup"], ["*"])
        self.assertEqual(json.loads(Path("app.json").read_text()), self.manifest)
        development["runtime-version"] = "99"
        Path("development.json").write_text(json.dumps(development))
        with self.assertRaises(ValueError):
            self.release.prepare("app.json", "v1.2.3", "main", "refs/heads/main", "owner/app", "development.json")

    def test_non_default_dispatch_and_invalid_tag_rejected(self):
        for tag, ref in [
            ("v1.2.3", "refs/heads/topic"),
            ("main", "refs/heads/main"),
            ("v1.2.3;echo unsafe", "refs/heads/main"),
        ]:
            with self.subTest(tag=tag, ref=ref), self.assertRaises(ValueError):
                self.prepare(tag, ref)

    def test_missing_and_unmerged_tags_rejected(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare("v9.9.9")
        self.git("checkout", "--orphan", "unmerged")
        self.git("add", "app.json")
        self.git("commit", "-qm", "Unmerged release")
        self.git("tag", "v2.0.0")
        self.git("checkout", "main")
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare("v2.0.0")

    def test_development_identity_rejected(self):
        self.manifest["app-id"] += ".Devel"
        self.write()
        with self.assertRaises(ValueError):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
