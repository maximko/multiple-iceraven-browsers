#!/usr/bin/env python3
"""Build configured IceRaven APK variants without editing upstream files."""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from read_config import read_config


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


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


def selected_variants(config: dict, names: str) -> list[dict]:
    variants = config["variants"]
    if names == "all":
        return variants

    wanted = {name.strip() for name in names.split(",") if name.strip()}
    by_id = {variant["id"]: variant for variant in variants}
    missing = sorted(wanted - set(by_id))
    if missing:
        raise ValueError(f"unknown variant id(s): {', '.join(missing)}")
    return [by_id[name] for name in wanted]


def clean_upstream_checkout(ref: str, source_dir: Path) -> None:
    run(["git", "checkout", "--force", ref], cwd=source_dir)
    run(["git", "submodule", "sync", "--recursive"], cwd=source_dir)
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=source_dir)
    run(["git", "reset", "--hard"], cwd=source_dir)
    run(["git", "submodule", "foreach", "--recursive", "git reset --hard"], cwd=source_dir)
    run(["git", "clean", "-fdx"], cwd=source_dir)
    run(["git", "submodule", "foreach", "--recursive", "git clean -fdx"], cwd=source_dir)


def ensure_parent_gradle_layout(source_dir: Path) -> None:
    source_gradle = source_dir / "gradle"
    expected_gradle = ROOT / "gradle"
    if not source_gradle.is_dir():
        raise RuntimeError(f"upstream Gradle directory does not exist: {source_gradle}")
    if expected_gradle.exists():
        return

    try:
        expected_gradle.symlink_to(source_gradle, target_is_directory=True)
    except OSError:
        shutil.copytree(source_gradle, expected_gradle)


def derive_version_from_ref(ref: str, fallback: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)+(?:[a-z]\d+)?)", ref)
    return match.group(1) if match else fallback


def ensure_mobile_android_version_file(source_dir: Path, ref: str, fallback: str) -> None:
    version_file = source_dir / "mobile" / "android" / "version.txt"
    if version_file.exists():
        return

    version_file.parent.mkdir(parents=True, exist_ok=True)
    version = os.environ.get("MOZILLA_VERSION") or derive_version_from_ref(ref, fallback)
    version_file.write_text(f"{version}\n", encoding="utf-8")


def install_android_sdk_pieces(source_dir: Path) -> None:
    script = source_dir / "automation" / "iceraven" / "install-sdk.sh"
    if script.is_file():
        run(["bash", str(script)], cwd=source_dir)


def patch_android_components(source_dir: Path) -> None:
    script = source_dir / "automation" / "iceraven" / "patch_android_components.sh"
    if script.is_file():
        run(["bash", str(script)], cwd=source_dir)


def replace_text(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in replacements:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def apply_release_string_fixes(source_dir: Path) -> None:
    patterns = [
        "app/src/*/res/values*/*strings.xml",
    ]
    for pattern in patterns:
        for raw_path in glob.glob(str(source_dir / pattern)):
            path = Path(raw_path)
            replace_text(
                path,
                [
                    ("Firefox", "Iceraven"),
                ],
            )
            text = path.read_text(encoding="utf-8")
            lines = []
            changed = False
            for line in text.splitlines(keepends=True):
                if "about_content" in line:
                    new_line = line.replace("Mozilla", "@forkmaintainers")
                    changed = changed or new_line != line
                    line = new_line
                lines.append(line)
            if changed:
                path.write_text("".join(lines), encoding="utf-8")
                text = path.read_text(encoding="utf-8")
            target = '<string name="trackers_blocked_panel_categorical_num_trackers_blocked">'
            if target in text:
                lines = []
                changed = False
                for line in text.splitlines(keepends=True):
                    if target in line:
                        new_line = line.replace("%s", "%1$s").replace("%d", "%2$d")
                        changed = changed or new_line != line
                        line = new_line
                    lines.append(line)
                if changed:
                    path.write_text("".join(lines), encoding="utf-8")


def validate_flavor_id(value: str) -> None:
    if not re.fullmatch(r"[a-z][A-Za-z0-9]*", value):
        raise ValueError(f"variant id must be a Gradle flavor name like 'personal' or 'workProfile': {value}")


def variant_task_name(variant: dict) -> str:
    flavor = variant["id"]
    return f"app:assemble{flavor[:1].upper()}{flavor[1:]}ForkRelease"


def variant_name(variant: dict) -> str:
    flavor = variant["id"]
    return f"{flavor[:1].upper()}{flavor[1:]}ForkRelease"


def lint_vital_exclusions(variants: list[dict]) -> list[str]:
    exclusions: list[str] = []
    for variant in variants:
        name = variant_name(variant)
        for task in (
            f"app:generate{name}LintVitalReportModel",
            f"app:lintVitalAnalyze{name}",
            f"app:lintVitalReport{name}",
            f"app:lintVital{name}",
        ):
            exclusions.extend(["-x", task])
    return exclusions


def write_variant_app_names(source_dir: Path, variants: list[dict]) -> None:
    for variant in variants:
        validate_flavor_id(variant["id"])
        values_dir = source_dir / "app" / "src" / f"{variant['id']}ForkRelease" / "res" / "values"
        values_dir.mkdir(parents=True, exist_ok=True)
        (values_dir / "static_strings.xml").write_text(
            "\n".join(
                [
                    '<?xml version="1.0" encoding="utf-8"?>',
                    "<resources>",
                    f'    <string name="app_name" translatable="false">{xml_escape(variant["appName"])}</string>',
                    "</resources>",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def ensure_upstream(repo: str, ref: str, source_dir: Path) -> None:
    if not (source_dir / ".git").exists():
        source_dir.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", repo, str(source_dir)])

    run(["git", "fetch", "--tags", "--prune", "origin"], cwd=source_dir)
    clean_upstream_checkout(ref, source_dir)
    ensure_parent_gradle_layout(source_dir)


def groovy_string(value: str) -> str:
    return json.dumps(value)


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def write_init_script(path: Path, variants: list[dict], abi: str) -> None:
    abi_value = groovy_string(abi)
    flavors = "\n".join(
        f"""
                androidExt.productFlavors.create({groovy_string(variant["id"])}) {{ flavor ->
                    flavor.dimension = "profile"
                    flavor.applicationId = {groovy_string(variant["applicationId"])}
                }}
""".rstrip()
        for variant in variants
    )
    nimbus_channels = "\n".join(
        f'                    nimbusExt.channels[{groovy_string(variant["id"] + "ForkRelease")}] = "release"'
        for variant in variants
    )
    path.write_text(
        f"""
allprojects {{
    plugins.withId("com.android.application") {{
        def configureAndroid = {{ androidExt ->
            if (!androidExt.flavorDimensions.contains("profile")) {{
                androidExt.flavorDimensions.add("profile")
            }}
{flavors}
            androidExt.splits.abi {{
                enable true
                reset()
                include {abi_value}
                universalApk false
            }}
        }}

        def androidComponentsExt = extensions.findByName("androidComponents")
        if (androidComponentsExt != null) {{
            androidComponentsExt.finalizeDsl {{ androidExt ->
                configureAndroid(androidExt)
            }}
        }} else {{
            project.afterEvaluate {{
                def androidExt = extensions.findByName("android")
                if (androidExt == null) {{
                    throw new GradleException("Android application extension was not found")
                }}
                configureAndroid(androidExt)
            }}
        }}

        project.afterEvaluate {{
            def nimbusExt = extensions.findByName("nimbus")
            if (nimbusExt != null && nimbusExt.hasProperty("channels")) {{
{nimbus_channels}
            }}
        }}
    }}
}}
""".lstrip(),
        encoding="utf-8",
    )


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or "variant"


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


def ensure_debug_keystore(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "keytool",
            "-genkeypair",
            "-storetype",
            "JKS",
            "-keystore",
            str(path),
            "-storepass",
            "android",
            "-alias",
            "androiddebugkey",
            "-keypass",
            "android",
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "10000",
            "-dname",
            "CN=Android Debug,O=Android,C=US",
        ]
    )


def sign_debug_apk(apk: Path, keystore: Path) -> None:
    apksigner = find_android_tool("apksigner")
    run(
        [
            str(apksigner),
            "sign",
            "--ks",
            str(keystore),
            "--ks-pass",
            "pass:android",
            "--ks-key-alias",
            "androiddebugkey",
            "--key-pass",
            "pass:android",
            str(apk),
        ]
    )


def collect_outputs(source_dir: Path, output_glob: str, artifact_dir: Path, variants: list[dict], ref: str, abi: str) -> list[Path]:
    all_apks = [path for path in source_dir.glob(output_glob) if path.is_file() and path.suffix == ".apk"]
    candidates = [
        path
        for path in all_apks
        if abi in path.name
    ]
    if not candidates:
        available = ", ".join(str(path) for path in all_apks) or "<none>"
        raise RuntimeError(f"no {abi} APK outputs matched {output_glob}; available APKs: {available}")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for variant in variants:
        variant_key = variant["id"].lower()
        matches = [
            apk
            for apk in candidates
            if variant_key in apk.name.lower() or variant_key in str(apk.parent).lower()
        ]
        if not matches:
            available = ", ".join(str(path) for path in candidates)
            raise RuntimeError(f"no {abi} APK output found for variant {variant['id']}; available APKs: {available}")
        for index, apk in enumerate(sorted(matches), start=1):
            suffix = "" if len(matches) == 1 else f"-{index}"
            target = artifact_dir / f"IceRaven-{safe_name(variant['id'])}-{safe_name(ref)}-{abi}{suffix}.apk"
            shutil.copy2(apk, target)
            copied.append(target)
    return copied


def write_build_metadata(artifact_dir: Path, ref: str) -> None:
    display_version = ref.removeprefix("iceraven-")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "build-metadata.env").write_text(
        "\n".join(
            [
                f"upstream_ref={ref}",
                f"release_tag=iceraven-variants-{safe_name(ref)}",
                f"release_name=IceRaven {display_version}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "variants.yml"))
    parser.add_argument("--source-dir", default=str(ROOT / ".work" / "iceraven-browser"))
    parser.add_argument("--artifacts-dir", default=str(ROOT / "artifacts"))
    parser.add_argument("--ref", help="Upstream tag, branch, or commit. Defaults to latest release.")
    parser.add_argument("--variants", default=os.environ.get("VARIANTS", "all"))
    args = parser.parse_args()

    config = read_config(Path(args.config))
    upstream = config["upstream"]
    ref = args.ref or upstream.get("ref", "latest-release")
    if ref == "latest-release":
        ref = latest_release_tag(upstream["releaseApi"])

    variants = selected_variants(config, args.variants)
    for variant in variants:
        validate_flavor_id(variant["id"])
    source_dir = Path(args.source_dir)
    artifact_dir = Path(args.artifacts_dir)
    abi = config["android"]["abi"]
    fallback_mozilla_version = config["android"].get("fallbackMozillaVersion", "0.0")
    sign_debug = config["build"].get("signDebug", "false").lower() == "true"
    debug_keystore = ROOT / ".work" / "debug.keystore"

    ensure_upstream(upstream["repo"], ref, source_dir)
    install_android_sdk_pieces(source_dir)
    ensure_mobile_android_version_file(source_dir, ref, fallback_mozilla_version)
    if sign_debug:
        ensure_debug_keystore(debug_keystore)

    print(f"Building {', '.join(variant['id'] for variant in variants)} for {ref}", flush=True)
    clean_upstream_checkout(ref, source_dir)
    ensure_parent_gradle_layout(source_dir)
    ensure_mobile_android_version_file(source_dir, ref, fallback_mozilla_version)
    patch_android_components(source_dir)
    apply_release_string_fixes(source_dir)
    write_variant_app_names(source_dir, variants)
    with tempfile.TemporaryDirectory(prefix="iceraven-gradle-") as temp_dir:
        init_script = Path(temp_dir) / "variant-init.gradle"
        write_init_script(init_script, variants, abi)
        run(
            [
                "./gradlew",
                "--no-daemon",
                "--max-workers",
                "2",
                "--stacktrace",
                "--init-script",
                str(init_script),
                *[variant_task_name(variant) for variant in variants],
                f"-PversionName={ref}",
                *lint_vital_exclusions(variants),
            ],
            cwd=source_dir,
        )

    built = collect_outputs(source_dir, config["build"]["outputGlob"], artifact_dir, variants, ref, abi)
    if sign_debug:
        for output in built:
            sign_debug_apk(output, debug_keystore)
    write_build_metadata(artifact_dir, ref)

    print("Built APK artifacts:")
    for path in built:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
