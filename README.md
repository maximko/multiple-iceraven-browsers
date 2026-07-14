<h1 align="center">Multiple IceRaven browsers</h1>

<p align="center">
  <img src="https://raw.githubusercontent.com/fork-maintainers/iceraven-browser/iceraven/app/src/forkRelease/res/mipmap-xxhdpi/ic_launcher.png" width="96" height="96" alt="IceRaven icon">
  <img src="https://raw.githubusercontent.com/fork-maintainers/iceraven-browser/iceraven/app/src/forkRelease/res/mipmap-xxhdpi/ic_launcher.png" width="96" height="96" alt="IceRaven icon">
  <img src="https://raw.githubusercontent.com/fork-maintainers/iceraven-browser/iceraven/app/src/forkRelease/res/mipmap-xxhdpi/ic_launcher.png" width="96" height="96" alt="IceRaven icon">
  <img src="https://raw.githubusercontent.com/fork-maintainers/iceraven-browser/iceraven/app/src/forkRelease/res/mipmap-xxhdpi/ic_launcher.png" width="96" height="96" alt="IceRaven icon">
</p>

Build multiple IceRaven Browser APKs with different package ids and app names to simulate Firefox profiles on Android.

<p align="center">
  <a href="https://github.com/maximko/multiple-iceraven-browsers/actions/workflows/daily-upstream-check.yml"><img src="https://github.com/maximko/multiple-iceraven-browsers/actions/workflows/daily-upstream-check.yml/badge.svg" alt="Daily upstream IceRaven check"></a>
</p>

## Info

This repository builds multiple IceRaven APK profiles from one upstream IceRaven
release. The upstream source is cloned during the build and is not committed here.

Fork this repo and edit `variants.yml` to add or remove APK profiles:

```yaml
variants:
  - id: personal
    appName: IceRaven Personal
    applicationId: org.iceraven.personal
```

All configured variants are built as `arm64-v8a` APKs only. The build script
generates Gradle product flavors from this file and builds the selected flavors
in one Gradle invocation.

The upstream `forkRelease` build type still appends IceRaven's package suffix,
so `org.iceraven.personal` becomes `org.iceraven.personal.iceraven`.

## Manual builds

Run the `Build IceRaven APKs` workflow from GitHub Actions. It always runs,
even when the latest upstream tag was already built.

Inputs:

- `upstream_ref`: use `latest-release`, a tag, branch, or commit.
- `variants`: use `all` or a comma-separated list like `personal,work`.

Successful builds upload APK artifacts and publish them to one GitHub Release
named like `IceRaven 2.45.0`.

## Daily upstream check

The `Daily upstream IceRaven check` workflow runs every day at 03:00 UTC. It
checks the latest IceRaven release tag and builds only when the tag differs from
`latest-upstream-tag.txt` stored on the separate `state` branch.

The workflow also has a manual `force_rebuild` input for testing the scheduled
path without waiting for a new upstream tag.
