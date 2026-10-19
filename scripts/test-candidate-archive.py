"""Small malicious-archive regressions; synthetic bytes, no executables run."""

import hashlib
import json
import runpy
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

audit = runpy.run_path(str(Path(__file__).with_name("verify-candidate-archive.py")))["audit"]


class CandidateArchiveTests(unittest.TestCase):
    def fixture(self, extra=(), payload=b"synthetic candidate", readonly=False, nested=False):
        temp = tempfile.TemporaryDirectory(prefix="easyai-archive-regression-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        path = root / "artifacts/win-unpacked/resources/lesson.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(payload)
        nested_name = "resources/backend/_internal/base_library.zip"
        nested_bytes = b"synthetic runtime library ZIP"
        if nested:
            nested_path = root / "artifacts/win-unpacked" / nested_name
            nested_path.parent.mkdir(parents=True)
            nested_path.write_bytes(nested_bytes)
        archive = root / "artifacts/easyai-0.0.0-win-x64.zip"
        with zipfile.ZipFile(archive, "w") as z:
            entry = zipfile.ZipInfo("resources/lesson.txt")
            entry.create_system = 0
            entry.external_attr = 0x21 if readonly else 0x20
            z.writestr(entry, payload)
            if nested:
                entry = zipfile.ZipInfo(nested_name)
                entry.create_system = 0
                entry.external_attr = 0x20
                z.writestr(entry, nested_bytes)
            for name, mode in extra:
                entry = zipfile.ZipInfo(name)
                entry.create_system = 3
                entry.external_attr = mode << 16
                z.writestr(entry, b"synthetic additional content")
        records = [
            {
                "path": "win-unpacked/resources/lesson.txt",
                "bytes": len(payload),
                "mode": 0o666,
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
            {
                "path": "easyai-0.0.0-win-x64.zip",
                "bytes": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            },
        ]
        if nested:
            records.append(
                {
                    "path": "win-unpacked/" + nested_name,
                    "bytes": len(nested_bytes),
                    "mode": 0o666,
                    "sha256": hashlib.sha256(nested_bytes).hexdigest(),
                }
            )
        manifest = {
            "schemaVersion": 2,
            "version": "0.0.0",
            "sourceCommit": "a" * 40,
            "platform": "win32",
            "arch": "x64",
            "distributionReady": False,
            "legalReviewComplete": False,
            "records": records,
        }
        (root / "builder-manifest.json").write_text(json.dumps(manifest))
        return root

    def test_windows_archive_has_exact_payload_and_readonly_contract(self):
        self.assertEqual(audit(self.fixture())["regularFiles"], 1)

    def test_nested_runtime_zip_is_exact_payload_not_distribution_archive(self):
        self.assertEqual(audit(self.fixture(nested=True))["regularFiles"], 2)

    def test_missing_misnamed_and_extra_root_archives_are_rejected(self):
        for variant in ["missing", "misnamed", "extra", "other-platform"]:
            with self.subTest(variant=variant):
                root = self.fixture(nested=True)
                p = root / "builder-manifest.json"
                manifest = json.loads(p.read_text())
                archive = manifest["records"][1]
                if variant == "missing":
                    manifest["records"].pop(1)
                elif variant == "misnamed":
                    archive["path"] = "wrong.zip"
                else:
                    manifest["records"].append(
                        {
                            **archive,
                            "path": "extra.zip"
                            if variant == "extra"
                            else "easyai-0.0.0-linux-x64.tar.gz",
                        }
                    )
                p.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, "ARCHIVE_MISSING"):
                    audit(root)

    def test_reject_readonly_drift(self):
        with self.assertRaisesRegex(ValueError, "READONLY_MISMATCH"):
            audit(self.fixture(readonly=True))

    def test_reject_traversal_drive_ads_backslash_aliases_and_extra_files(self):
        for name in [
            "../outside",
            "resources/CON.txt",
            "C:/outside",
            "resources/lesson.txt:stream",
            "resources\\outside",
            "resources/lesson.txt.",
            "resources/lesson.txt ",
            "RESOURCES/LESSON.TXT",
            "resources/extra.txt",
            "resources/./extra.txt",
            "resources//extra.txt",
        ]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                audit(self.fixture([(name, stat.S_IFREG | 0o644)]))

    def test_reject_links_special_types_and_forged_directories(self):
        for name, mode in [
            ("resources/link", stat.S_IFLNK | 0o777),
            ("resources/device", stat.S_IFCHR | 0o600),
            ("resources/extra/", stat.S_IFDIR | 0o755),
        ]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                audit(self.fixture([(name, mode)]))

    def test_reject_payload_drift_even_with_archive_hash_updated(self):
        root = self.fixture()
        p = root / "builder-manifest.json"
        manifest = json.loads(p.read_text())
        manifest["records"][0]["sha256"] = "0" * 64
        p.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "BYTES_MISMATCH"):
            audit(root)

    def test_known_secret_feature_is_blocked_without_printing_value(self):
        root = self.fixture(payload=b"ghp_" + b"A" * 36)
        with self.assertRaisesRegex(ValueError, "CANDIDATE_SECRET_FEATURE"):
            audit(root)


if __name__ == "__main__":
    unittest.main()
