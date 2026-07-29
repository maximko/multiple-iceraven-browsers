#!/usr/bin/env python3
"""Sign built APKs with the repository's persistent Android signing key."""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIGNING_KEYSTORE_ENV = "ANDROID_SIGNING_KEYSTORE_BASE64"
SIGNING_PASSWORD_ENV = "ANDROID_SIGNING_PASSWORD"
SIGNING_KEY_ALIAS = "iceraven"


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def find_android_tool(name: str) -> Path:
    sdk_roots = [
        os.environ.get("ANDROID_HOME"),
        os.environ.get("ANDROID_SDK_ROOT"),
        "/usr/local/lib/android/sdk",
        "/opt/android-sdk",
    ]
    candidates: list[Path] = []
    for root in sdk_roots:
        if not root:
            continue
        candidates.extend(Path(root).glob(f"build-tools/*/{name}"))
    if not candidates:
        raise RuntimeError(f"could not find Android SDK tool: {name}")
    return sorted(candidates)[-1]


def decode_signing_keystore(path: Path) -> None:
    encoded_keystore = os.environ.get(SIGNING_KEYSTORE_ENV, "").strip()
    signing_password = os.environ.get(SIGNING_PASSWORD_ENV, "")
    missing = [
        name
        for name, value in (
            (SIGNING_KEYSTORE_ENV, encoded_keystore),
            (SIGNING_PASSWORD_ENV, signing_password),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "missing required Android signing secret(s): "
            f"{', '.join(missing)}; see README.md#android-signing-key"
        )

    try:
        keystore_bytes = base64.b64decode(encoded_keystore, validate=True)
    except (binascii.Error, ValueError) as error:
        raise RuntimeError(f"{SIGNING_KEYSTORE_ENV} is not valid base64") from error
    if not keystore_bytes:
        raise RuntimeError(f"{SIGNING_KEYSTORE_ENV} decoded to an empty keystore")

    path.write_bytes(keystore_bytes)
    path.chmod(0o600)
    run(
        [
            "keytool",
            "-list",
            "-keystore",
            str(path),
            "-storepass:env",
            SIGNING_PASSWORD_ENV,
            "-alias",
            SIGNING_KEY_ALIAS,
        ]
    )


def sign_apk(apk: Path, keystore: Path, apksigner: Path) -> None:
    run(
        [
            str(apksigner),
            "sign",
            "--ks",
            str(keystore),
            "--ks-pass",
            f"env:{SIGNING_PASSWORD_ENV}",
            "--ks-key-alias",
            SIGNING_KEY_ALIAS,
            "--key-pass",
            f"env:{SIGNING_PASSWORD_ENV}",
            str(apk),
        ]
    )
    run([str(apksigner), "verify", "--verbose", "--print-certs", str(apk)])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("apks", nargs="*", type=Path, help="APKs to sign; defaults to artifacts/*.apk")
    args = parser.parse_args()

    apks = args.apks or sorted((ROOT / "artifacts").glob("*.apk"))
    missing_apks = [str(apk) for apk in apks if not apk.is_file()]
    if missing_apks:
        raise RuntimeError(f"APK file(s) do not exist: {', '.join(missing_apks)}")
    if not apks:
        raise RuntimeError("no APKs found to sign")

    apksigner = find_android_tool("apksigner")
    runner_temp = os.environ.get("RUNNER_TEMP")
    with tempfile.TemporaryDirectory(prefix="iceraven-signing-", dir=runner_temp) as temp_dir:
        keystore = Path(temp_dir) / "iceraven-signing.p12"
        decode_signing_keystore(keystore)
        for apk in apks:
            sign_apk(apk, keystore, apksigner)

    print("Signed APK artifacts:")
    for apk in apks:
        print(apk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
