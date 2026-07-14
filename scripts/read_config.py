#!/usr/bin/env python3
"""Read the small variants.yml format used by this repository."""

from __future__ import annotations

from pathlib import Path


def _clean_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def read_config(path: Path) -> dict:
    config: dict = {}
    current_section: str | None = None
    current_item: dict | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        if not line.startswith(" "):
            key, _, value = line.partition(":")
            current_section = key.strip()
            current_item = None
            if value.strip():
                config[current_section] = _clean_value(value)
            elif current_section == "variants":
                config[current_section] = []
            else:
                config[current_section] = {}
            continue

        if current_section is None:
            raise ValueError(f"YAML value without section: {raw_line}")

        stripped = line.strip()
        if stripped.startswith("- "):
            if current_section != "variants":
                raise ValueError(f"Only variants may contain list items: {raw_line}")
            current_item = {}
            config[current_section].append(current_item)
            stripped = stripped[2:].strip()
            if not stripped:
                continue
            key, sep, value = stripped.partition(":")
            if not sep:
                raise ValueError(f"Invalid variant entry: {raw_line}")
            current_item[key.strip()] = _clean_value(value)
            continue

        key, sep, value = stripped.partition(":")
        if not sep:
            raise ValueError(f"Invalid YAML line: {raw_line}")
        target = current_item if current_item is not None else config[current_section]
        target[key.strip()] = _clean_value(value)

    return config
