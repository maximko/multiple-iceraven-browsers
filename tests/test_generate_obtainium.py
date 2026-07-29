from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
MODULE_PATH = SCRIPTS_DIR / "generate-obtainium.py"
SPEC = importlib.util.spec_from_file_location("generate_obtainium", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
generate_obtainium = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_obtainium)


class ObtainiumImportTests(unittest.TestCase):
    config = {
        "android": {"abi": "arm64-v8a"},
        "variants": [
            {
                "id": "direct",
                "appName": "Direct",
                "applicationId": "org.example.direct",
            },
            {
                "id": "banking",
                "appName": "Banking",
                "applicationId": "org.example.banking",
            },
        ],
    }

    def test_builds_one_distinct_entry_per_variant(self) -> None:
        payload = generate_obtainium.build_import(self.config, "owner/repository")

        self.assertEqual(len(payload["apps"]), 2)
        self.assertEqual(
            {app["id"] for app in payload["apps"]},
            {"org.example.direct.iceraven", "org.example.banking.iceraven"},
        )
        self.assertTrue(
            all(
                app["url"] == "https://github.com/owner/repository"
                for app in payload["apps"]
            )
        )
        self.assertTrue(all(app["author"] == "owner" for app in payload["apps"]))
        self.assertTrue(all(app["preferredApkIndex"] == 0 for app in payload["apps"]))

    def test_filter_selects_only_the_matching_variant(self) -> None:
        payload = generate_obtainium.build_import(self.config, "owner/repository")
        direct = next(app for app in payload["apps"] if app["name"] == "Direct")
        settings = json.loads(direct["additionalSettings"])
        apk_filter = re.compile(settings["apkFilterRegEx"])

        self.assertEqual(
            settings["apkFilterRegEx"],
            r"^IceRaven-direct-.+-arm64-v8a(?:-[0-9]+)?\.apk$",
        )
        self.assertIsNotNone(
            apk_filter.fullmatch("IceRaven-direct-iceraven-2.46.0-arm64-v8a.apk")
        )
        self.assertIsNotNone(
            apk_filter.fullmatch("IceRaven-direct-feature-test-arm64-v8a-1.apk")
        )
        self.assertIsNotNone(
            apk_filter.fullmatch("IceRaven-direct-feature-test-arm64-v8a-2.apk")
        )
        self.assertIsNone(
            apk_filter.fullmatch("IceRaven-banking-iceraven-2.46.0-arm64-v8a.apk")
        )
        self.assertFalse(settings["invertAPKFilter"])
        self.assertFalse(settings["autoApkFilterByArch"])
        self.assertTrue(settings["fallbackToOlderReleases"])
        self.assertEqual(settings["appName"], "Direct")
        version_match = re.fullmatch(
            settings["versionExtractionRegEx"],
            "iceraven-variants-iceraven-2.46.0",
        )
        self.assertIsNotNone(version_match)
        assert version_match is not None
        self.assertEqual(version_match.group(1), "iceraven-2.46.0")
        self.assertEqual(settings["matchGroupToUse"], "$1")
        self.assertTrue(settings["naiveStandardVersionDetection"])
        self.assertTrue(settings["versionDetection"])

    def test_release_artifacts_match_one_entry_each(self) -> None:
        payload = generate_obtainium.build_import(self.config, "owner/repository")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            (artifacts_dir / "IceRaven-direct-iceraven-2.46.0-arm64-v8a.apk").touch()
            (artifacts_dir / "IceRaven-banking-iceraven-2.46.0-arm64-v8a.apk").touch()

            generate_obtainium.validate_release_artifacts(payload, artifacts_dir)

    def test_ambiguous_release_artifacts_are_rejected(self) -> None:
        payload = generate_obtainium.build_import(self.config, "owner/repository")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            (artifacts_dir / "IceRaven-direct-iceraven-2.46.0-arm64-v8a-1.apk").touch()
            (artifacts_dir / "IceRaven-direct-iceraven-2.46.0-arm64-v8a-2.apk").touch()

            with self.assertRaisesRegex(ValueError, "matches multiple APK artifacts"):
                generate_obtainium.validate_release_artifacts(payload, artifacts_dir)

    def test_duplicate_final_package_ids_are_rejected(self) -> None:
        config = {
            "android": {"abi": "arm64-v8a"},
            "variants": [self.config["variants"][0], self.config["variants"][0]],
        }

        with self.assertRaisesRegex(ValueError, "duplicate Android application IDs"):
            generate_obtainium.build_import(config, "owner/repository")

    def test_invalid_repository_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "owner/name"):
            generate_obtainium.build_import(self.config, "https://github.com/owner/repository")


if __name__ == "__main__":
    unittest.main()
