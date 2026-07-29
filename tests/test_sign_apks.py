from __future__ import annotations

import base64
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sign-apks.py"
SPEC = importlib.util.spec_from_file_location("sign_apks", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
sign_apks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sign_apks)


class SigningTests(unittest.TestCase):
    def test_missing_secrets_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "missing required Android signing secret"):
                    sign_apks.decode_signing_keystore(Path(temp_dir) / "key.p12")

    def test_invalid_base64_is_rejected(self) -> None:
        environment = {
            sign_apks.SIGNING_KEYSTORE_ENV: "not base64!",
            sign_apks.SIGNING_PASSWORD_ENV: "test-password",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(RuntimeError, "not valid base64"):
                    sign_apks.decode_signing_keystore(Path(temp_dir) / "key.p12")

    @mock.patch.object(sign_apks, "run")
    def test_keystore_is_private_and_password_stays_out_of_command(self, run: mock.Mock) -> None:
        keystore_bytes = b"test keystore bytes"
        password = "secret-that-must-not-be-logged"
        environment = {
            sign_apks.SIGNING_KEYSTORE_ENV: base64.b64encode(keystore_bytes).decode("ascii"),
            sign_apks.SIGNING_PASSWORD_ENV: password,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            keystore = Path(temp_dir) / "key.p12"
            with mock.patch.dict(os.environ, environment, clear=True):
                sign_apks.decode_signing_keystore(keystore)

            self.assertEqual(keystore.read_bytes(), keystore_bytes)
            self.assertEqual(keystore.stat().st_mode & 0o777, 0o600)

        command = run.call_args.args[0]
        self.assertIn("-storepass:env", command)
        self.assertIn(sign_apks.SIGNING_PASSWORD_ENV, command)
        self.assertNotIn(password, command)

    @mock.patch.object(sign_apks, "run")
    def test_apk_is_signed_and_verified_without_password_in_arguments(self, run: mock.Mock) -> None:
        sign_apks.sign_apk(Path("app.apk"), Path("key.p12"), Path("apksigner"))

        self.assertEqual(run.call_count, 2)
        sign_command = run.call_args_list[0].args[0]
        verify_command = run.call_args_list[1].args[0]
        self.assertIn("env:ANDROID_SIGNING_PASSWORD", sign_command)
        self.assertEqual(verify_command[1:4], ["verify", "--verbose", "--print-certs"])


if __name__ == "__main__":
    unittest.main()
