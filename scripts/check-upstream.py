#!/usr/bin/env python3
"""Print the latest IceRaven release tag and whether it should be built."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from read_config import read_config


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
    parser.add_argument("--state-file", default="state/latest-upstream-tag.txt")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--update-state", action="store_true")
    args = parser.parse_args()

    config = read_config(Path(args.config))
    tag = latest_release_tag(config["upstream"]["releaseApi"])
    state_path = Path(args.state_file)
    previous = state_path.read_text(encoding="utf-8").strip() if state_path.exists() else ""
    should_build = args.force or tag != previous

    if args.update_state and should_build:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(f"{tag}\n", encoding="utf-8")

    values = {
        "latest_tag": tag,
        "previous_tag": previous,
        "should_build": "true" if should_build else "false",
    }
    write_github_output(values)
    print(json.dumps(values, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
