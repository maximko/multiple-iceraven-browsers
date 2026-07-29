from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_metadata  # noqa: E402


class ReleaseMetadataTests(unittest.TestCase):
    def test_exact_ref_does_not_query_latest_release(self) -> None:
        with mock.patch.object(release_metadata, "latest_release_tag") as latest_release_tag:
            resolved = release_metadata.resolve_upstream_ref("iceraven-2.46.0", "unused")

        self.assertEqual(resolved, "iceraven-2.46.0")
        latest_release_tag.assert_not_called()

    def test_latest_release_is_resolved_once(self) -> None:
        with mock.patch.object(
            release_metadata,
            "latest_release_tag",
            return_value="iceraven-2.46.0",
        ) as latest_release_tag:
            resolved = release_metadata.resolve_upstream_ref("latest-release", "https://example.test")

        self.assertEqual(resolved, "iceraven-2.46.0")
        latest_release_tag.assert_called_once_with("https://example.test")

    def test_line_breaks_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "without line breaks"):
            release_metadata.validate_ref("iceraven-2.46.0\nrelease_tag=unexpected")

    def test_release_metadata_uses_fixed_tag_namespace(self) -> None:
        metadata = release_metadata.metadata_for_ref("feature/test")

        self.assertEqual(metadata["upstream_ref"], "feature/test")
        self.assertEqual(metadata["release_tag"], "iceraven-variants-feature-test")
        self.assertEqual(metadata["release_name"], "IceRaven feature/test")


if __name__ == "__main__":
    unittest.main()
