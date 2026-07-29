#!/usr/bin/env python3
"""Resolve an upstream ref and emit trusted release metadata."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from read_config import read_config


RELEASE_TAG_PREFIX = "iceraven-variants-"


def latest_release_tag(api_url: str) -> str:
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "iceraven-builds",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    tag = payload.get("tag_name")
    if not tag:
        raise RuntimeError(f"release response from {api_url} did not contain tag_name")
    return tag


def validate_ref(ref: str) -> str:
    if not ref or len(ref) > 255 or any(character in ref for character in "\r\n\0"):
        raise ValueError("upstream ref must be 1-255 characters without line breaks or NUL")
    return ref


def resolve_upstream_ref(ref: str, api_url: str) -> str:
    resolved = latest_release_tag(api_url) if ref == "latest-release" else ref
    return validate_ref(resolved)


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or "variant"


def version_name_for_ref(ref: str) -> str:
    return safe_name(validate_ref(ref))


def metadata_for_ref(ref: str) -> dict[str, str]:
    ref = validate_ref(ref)
    version_name = version_name_for_ref(ref)
    return {
        "upstream_ref": ref,
        "release_tag": f"{RELEASE_TAG_PREFIX}{version_name}",
        "release_name": f"IceRaven {ref.removeprefix('iceraven-')}",
    }


def write_github_output(values: dict[str, str]) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with Path(output).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="variants.yml")
    parser.add_argument("--ref", required=True)
    args = parser.parse_args()

    config = read_config(Path(args.config))
    ref = resolve_upstream_ref(args.ref, config["upstream"]["releaseApi"])
    metadata = metadata_for_ref(ref)
    write_github_output(metadata)
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
