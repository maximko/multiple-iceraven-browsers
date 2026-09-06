from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
MODULE_PATH = SCRIPTS_DIR / "build-variants.py"
SPEC = importlib.util.spec_from_file_location("build_variants", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
build_variants = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_variants)


class PythonEnvironmentTests(unittest.TestCase):
    def test_missing_upstream_setup_script_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(build_variants, "run") as run:
                build_variants.setup_python_environment(Path(temp_dir))

        run.assert_not_called()

    def test_upstream_setup_script_creates_expected_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            script = source_dir / "automation" / "iceraven" / "setup_venv.sh"
            script.parent.mkdir(parents=True)
            script.touch()

            def create_environment(command: list[str], cwd: Path | None = None) -> None:
                self.assertEqual(command, ["bash", str(script)])
                self.assertEqual(cwd, source_dir)
                python = source_dir / "venv" / "bin" / "python"
                python.parent.mkdir(parents=True)
                python.touch()

            with mock.patch.object(build_variants, "run", side_effect=create_environment):
                build_variants.setup_python_environment(source_dir)

    def test_incomplete_upstream_environment_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            script = source_dir / "automation" / "iceraven" / "setup_venv.sh"
            script.parent.mkdir(parents=True)
            script.touch()

            with mock.patch.object(build_variants, "run"):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "upstream Python environment was not created",
                ):
                    build_variants.setup_python_environment(source_dir)


if __name__ == "__main__":
    unittest.main()
