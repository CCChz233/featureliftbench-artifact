from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.dependency_install import build_pip_install_lock_command
from featureliftbench.dependency_install import install_dependency_lock
from featureliftbench.dependency_install import sanity_vendor_wheels_ready
from featureliftbench.dependency_install import validate_lock_dependencies


class DependencyInstallTests(unittest.TestCase):
    def test_validate_lock_dependencies_rejects_forbidden(self) -> None:
        metadata = {
            "environment": {
                "allowed_dependencies": ["text-unidecode"],
                "forbidden_dependencies": ["text-unidecode"],
            }
        }
        errors = validate_lock_dependencies(metadata, ["text-unidecode"])
        self.assertTrue(errors)

    def test_build_pip_install_lock_command_uses_vendor_wheels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wheels = Path(tmp) / "vendor-wheels"
            wheels.mkdir()
            (wheels / "text_unidecode-1.3-py3-none-any.whl").write_text("wheel", encoding="utf-8")
            lock_path = Path(tmp) / "requirements.lock"
            lock_path.write_text("text-unidecode==1.3\n", encoding="utf-8")

            with mock.patch("featureliftbench.dependency_install.VENDOR_WHEELS_DIR", wheels):
                command = build_pip_install_lock_command(
                    venv_python=Path(tmp) / "python",
                    lock_path=lock_path,
                )

            self.assertIn("--find-links", command)
            self.assertIn(str(wheels.resolve()), command)

    def test_sanity_vendor_wheels_ready_after_bootstrap_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wheels = Path(tmp)
            (wheels / "text_unidecode-1.3-py3-none-any.whl").write_text("wheel", encoding="utf-8")
            with mock.patch("featureliftbench.dependency_install.VENDOR_WHEELS_DIR", wheels):
                ready, missing = sanity_vendor_wheels_ready()
            self.assertTrue(ready)
            self.assertEqual(missing, [])

    def test_vendor_wheel_present_ignores_macos_only_wheels(self) -> None:
        from featureliftbench.dependency_install import vendor_wheel_present

        with tempfile.TemporaryDirectory() as tmp:
            wheels = Path(tmp)
            (wheels / "markupsafe-2.1.5-cp312-cp312-macosx_10_9_universal2.whl").write_text(
                "wheel",
                encoding="utf-8",
            )
            with mock.patch("featureliftbench.dependency_install.VENDOR_WHEELS_DIR", wheels):
                self.assertFalse(vendor_wheel_present("markupsafe"))

            (wheels / "markupsafe-2.1.5-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl").write_text(
                "wheel",
                encoding="utf-8",
            )
            with mock.patch("featureliftbench.dependency_install.VENDOR_WHEELS_DIR", wheels):
                self.assertTrue(vendor_wheel_present("markupsafe"))
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "requirements.lock").write_text("\n", encoding="utf-8")
            metadata = {"environment": {"dependency_lock": "requirements.lock", "allowed_dependencies": []}}
            result = install_dependency_lock(
                venv_python=Path(sys.executable),
                task_path=task_dir,
                metadata=metadata,
                cwd=task_dir,
                env={},
                timeout_seconds=30,
            )
            self.assertTrue(result.skipped)
            self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
