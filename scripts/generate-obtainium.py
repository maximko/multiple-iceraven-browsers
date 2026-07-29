#!/usr/bin/env python3
"""Generate an Obtainium import with one filtered entry per IceRaven variant."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from read_config import read_config
from release_metadata import RELEASE_TAG_PREFIX, safe_name


ROOT = Path(__file__).resolve().parents[1]
# IceRaven's upstream forkRelease build type appends this to each configured base ID.
ICERAVEN_APPLICATION_ID_SUFFIX = ".iceraven"
REGEXP_SPECIAL_CHARACTERS = frozenset(r"\^$.|?*+()[]{}")


def validate_repository(repository: str) -> str:
    repository = repository.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("repository must use the GitHub owner/name format")
    return repository


def escape_regexp(value: str) -> str:
    """Escape a literal for Dart's RegExp without escaping ordinary hyphens."""
    return "".join(
        f"\\{character}" if character in REGEXP_SPECIAL_CHARACTERS else character
        for character in value
    )


def app_entry(variant: dict, repository: str, abi: str) -> dict:
    variant_id = variant["id"]
    app_name = variant["appName"]
    application_id = variant["applicationId"] + ICERAVEN_APPLICATION_ID_SUFFIX
    artifact_variant_id = safe_name(variant_id)
    apk_filter = (
        rf"^IceRaven-{escape_regexp(artifact_variant_id)}-.+-{escape_regexp(abi)}"
        rf"(?:-[0-9]+)?\.apk$"
    )
    additional_settings = {
        "apkFilterRegEx": apk_filter,
        "invertAPKFilter": False,
        "autoApkFilterByArch": False,
        "fallbackToOlderReleases": True,
        "appName": app_name,
        "versionExtractionRegEx": rf"^{escape_regexp(RELEASE_TAG_PREFIX)}(.+)$",
        "matchGroupToUse": "$1",
        "naiveStandardVersionDetection": True,
        "versionDetection": True,
    }

    return {
        "id": application_id,
        "url": f"https://github.com/{repository}",
        "author": repository.split("/", 1)[0],
        "name": app_name,
        "preferredApkIndex": 0,
        # Obtainium's import format stores additionalSettings as encoded JSON.
        "additionalSettings": json.dumps(
            additional_settings,
            separators=(",", ":"),
            sort_keys=True,
        ),
    }


def build_import(config: dict, repository: str) -> dict:
    repository = validate_repository(repository)
    abi = config["android"]["abi"]
    apps = [app_entry(variant, repository, abi) for variant in config["variants"]]
    app_ids = [app["id"] for app in apps]
    if len(app_ids) != len(set(app_ids)):
        raise ValueError("configured variants produce duplicate Android application IDs")
    return {"apps": apps}


def validate_release_artifacts(payload: dict, artifacts_dir: Path) -> None:
    apk_names = sorted(path.name for path in artifacts_dir.glob("*.apk") if path.is_file())
    matches_by_app: dict[str, list[str]] = {app["id"]: [] for app in payload["apps"]}

    for apk_name in apk_names:
        matching_apps = []
        for app in payload["apps"]:
            settings = json.loads(app["additionalSettings"])
            if re.fullmatch(settings["apkFilterRegEx"], apk_name):
                matching_apps.append(app)
                matches_by_app[app["id"]].append(apk_name)
        if len(matching_apps) != 1:
            raise ValueError(
                f"APK artifact must match exactly one Obtainium entry: {apk_name}"
            )

    ambiguous = {
        app_id: matches
        for app_id, matches in matches_by_app.items()
        if len(matches) > 1
    }
    if ambiguous:
        details = "; ".join(
            f"{app_id}: {', '.join(matches)}"
            for app_id, matches in ambiguous.items()
        )
        raise ValueError(f"Obtainium filter matches multiple APK artifacts: {details}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "variants.yml"))
    parser.add_argument("--repository", required=True, help="GitHub repository in owner/name form")
    parser.add_argument("--artifacts-dir", default=str(ROOT / "artifacts"))
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "obtainium.json"))
    args = parser.parse_args()

    config = read_config(Path(args.config))
    payload = build_import(config, args.repository)
    artifacts_dir = Path(args.artifacts_dir)
    if artifacts_dir.exists():
        validate_release_artifacts(payload, artifacts_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Generated Obtainium import: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
