"""Exercise validation reports through the installed command-line interface."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dcatus_validator.validate import validate_catalog, validate_datasets

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {"v1.1": "dcat1-sample.json", "v3.0": "dcat3-sample.json"}


class TestValidationReports(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "catalog.json"
        self.report = self.root / "report.json"

    def sample(self, version):
        return json.loads((ROOT / "test_json" / SAMPLES[version]).read_text())

    def run_cli(self, catalog, version, use_default=False):
        self.source.write_text(json.dumps(catalog), encoding="utf-8")
        original = self.source.read_bytes()
        args = [
            sys.executable,
            "-m",
            "dcatus_validator.validate",
            str(self.source),
            "-s",
            version,
        ]
        if not use_default:
            args.extend(["-o", str(self.report)])
        result = subprocess.run(
            args, cwd=self.root, text=True, capture_output=True, timeout=15
        )
        self.assertEqual(self.source.read_bytes(), original)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_invalid_datasets_produce_the_documented_report(self):
        for version in SAMPLES:
            with self.subTest(version=version):
                catalog = self.sample(version)
                valid = copy.deepcopy(catalog["dataset"][0])
                invalid = copy.deepcopy(valid)
                invalid["title"] = "Invalid café dataset"
                del invalid["description"]
                catalog["dataset"] = [valid, invalid]
                result = self.run_cli(catalog, version)
                self.assertEqual(result.returncode, 1)
                self.assertTrue(self.report.exists(), result.stderr)
                self.assertEqual(
                    json.loads(self.report.read_text()),
                    validate_datasets(catalog["dataset"], version),
                )
                self.assertNotIn("All datasets are valid.", result.stderr)
                self.report.unlink()

    def test_default_report_name_is_used(self):
        for version in SAMPLES:
            with self.subTest(version=version):
                catalog = self.sample(version)
                del catalog["dataset"][0]["description"]
                result = self.run_cli(catalog, version, use_default=True)
                self.assertEqual(result.returncode, 1)
                default = self.root / "invalid_datasets.json"
                self.assertTrue(default.exists(), result.stderr)
                self.assertEqual(
                    json.loads(default.read_text()),
                    validate_datasets(catalog["dataset"], version),
                )
                default.unlink()

    def test_catalog_and_dataset_errors_still_produce_a_dataset_report(self):
        for version in SAMPLES:
            with self.subTest(version=version):
                catalog = self.sample(version)
                catalog["conformsTo"] = 7
                del catalog["dataset"][0]["description"]
                self.assertTrue(validate_catalog(catalog, version))
                result = self.run_cli(catalog, version)
                self.assertEqual(result.returncode, 1)
                self.assertTrue(self.report.exists(), result.stderr)
                self.assertIn("conformsTo", result.stderr)
                self.report.unlink()

    def test_catalog_only_errors_remain_failures_and_preserve_old_report(self):
        for version in SAMPLES:
            with self.subTest(version=version):
                catalog = self.sample(version)
                catalog["conformsTo"] = 7
                self.report.write_bytes(b"existing report")
                result = self.run_cli(catalog, version)
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("All datasets are valid.", result.stderr)
                self.assertEqual(self.report.read_bytes(), b"existing report")

    def test_invalid_dataset_container_is_not_iterated(self):
        for version in SAMPLES:
            for invalid in (None, "not an array", 5, {"title": "not an array"}):
                with self.subTest(version=version, invalid=invalid):
                    catalog = self.sample(version)
                    catalog["dataset"] = invalid
                    result = self.run_cli(catalog, version)
                    self.assertEqual(result.returncode, 1)
                    self.assertFalse(self.report.exists())

    def test_non_object_dataset_entries_are_reported(self):
        for version in SAMPLES:
            with self.subTest(version=version):
                catalog = self.sample(version)
                catalog["dataset"].extend([None, 7, "invalid", []])
                result = self.run_cli(catalog, version)
                self.assertEqual(result.returncode, 1)
                self.assertTrue(self.report.exists(), result.stderr)
                report = json.loads(self.report.read_text())
                self.assertEqual(len(report), 4)
                self.assertTrue(
                    all(entry["title"] == "Unknown Title" for entry in report)
                )
                self.assertTrue(all(entry["errors"] for entry in report))
                self.report.unlink()

    def test_valid_catalog_does_not_write_or_replace_a_report(self):
        for version in SAMPLES:
            with self.subTest(version=version):
                self.report.write_bytes(b"existing report")
                result = self.run_cli(self.sample(version), version)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("All datasets are valid.", result.stderr)
                self.assertEqual(self.report.read_bytes(), b"existing report")

    def test_non_object_catalog_is_a_validation_failure(self):
        for document in (None, [], 123, "not an object"):
            with self.subTest(document=document):
                result = self.run_cli(document, "v3.0")
                self.assertEqual(result.returncode, 1)
                self.assertFalse(self.report.exists())

    def test_invalid_json_remains_a_load_failure(self):
        self.source.write_text("{invalid json}")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "dcatus_validator.validate",
                str(self.source),
                "-o",
                str(self.report),
            ],
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.report.exists())


if __name__ == "__main__":
    unittest.main()
