from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts/reorganize_experiments.py"
_SPEC = importlib.util.spec_from_file_location("reorganize_experiments", _SCRIPT)
assert _SPEC and _SPEC.loader
reorganize = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = reorganize
_SPEC.loader.exec_module(reorganize)


class ReorganizeExperimentsTests(unittest.TestCase):
    def test_safe_tar_allows_internal_parent_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "safe.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                data = b"readme"
                readme = tarfile.TarInfo("pkg/README.md")
                readme.size = len(data)
                handle.addfile(readme, io.BytesIO(data))
                link = tarfile.TarInfo("pkg/docs/index.md")
                link.type = tarfile.SYMTYPE
                link.linkname = "../README.md"
                handle.addfile(link)
            self.assertEqual(reorganize.safe_tar(archive), (True, "ok"))

    def test_safe_tar_rejects_archive_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                link = tarfile.TarInfo("pkg/link")
                link.type = tarfile.SYMTYPE
                link.linkname = "../../outside"
                handle.addfile(link)
            safe, detail = reorganize.safe_tar(archive)
            self.assertFalse(safe)
            self.assertIn("unsafe link", detail)

    def test_move_manifest_has_unique_destinations(self) -> None:
        moves = reorganize._moves()
        destinations = [move.destination for move in moves]
        self.assertEqual(len(destinations), len(set(destinations)))

    def test_migration_refuses_destination_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source").mkdir()
            (root / "destination").mkdir()
            with patch.object(reorganize, "ROOT", root):
                with self.assertRaisesRegex(RuntimeError, "migration collision"):
                    reorganize.migrate(
                        [reorganize.Move("source", "destination", "test")]
                    )

    def test_bundle_sha_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "bundle.tar.gz"
            with tarfile.open(archive, "w:gz"):
                pass
            bundle = reorganize.RetiredBundle(
                filename=archive.name,
                sha256="0" * 64,
                reason="test",
            )
            verified, checks = reorganize.verify_bundle(bundle, archive)
            self.assertFalse(verified)
            self.assertIn("sha256 mismatch", checks[0])


if __name__ == "__main__":
    unittest.main()
