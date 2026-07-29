<h1 align="center">Multiple IceRaven browsers</h1>

<p align="center">
  <img src="https://raw.githubusercontent.com/fork-maintainers/iceraven-browser/iceraven/app/src/forkRelease/res/mipmap-xxhdpi/ic_launcher.png" width="96" height="96" alt="IceRaven icon">
  <img src="https://raw.githubusercontent.com/fork-maintainers/iceraven-browser/iceraven/app/src/forkRelease/res/mipmap-xxhdpi/ic_launcher.png" width="96" height="96" alt="IceRaven icon">
  <img src="https://raw.githubusercontent.com/fork-maintainers/iceraven-browser/iceraven/app/src/forkRelease/res/mipmap-xxhdpi/ic_launcher.png" width="96" height="96" alt="IceRaven icon">
  <img src="https://raw.githubusercontent.com/fork-maintainers/iceraven-browser/iceraven/app/src/forkRelease/res/mipmap-xxhdpi/ic_launcher.png" width="96" height="96" alt="IceRaven icon">
</p>

Build multiple IceRaven Browser APKs with different package ids and app names to simulate Firefox profiles on Android.

<p align="center">
  <a href="https://github.com/maximko/multiple-iceraven-browsers/releases/latest/download/obtainium.json"><img src="https://raw.githubusercontent.com/ImranR98/Obtainium/main/assets/graphics/badge_obtainium.png" alt="Get it on Obtainium" height="108"></a>
</p>

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

## Obtainium updates

Every new GitHub Release includes `obtainium.json`, generated from `variants.yml`.
It contains one entry per variant, using the variant's real Android package id
and an APK filename filter. This lets Obtainium select the matching APK instead
of asking which variant to download on every update.

Import it once:

1. Use the badge above to download `obtainium.json` from the latest release, or
   download it from any individual GitHub Release.
2. Open Obtainium's **Import/Export** page and import the downloaded file.
3. Keep the variants you use and delete any unwanted entries.
4. Run one update check so Obtainium loads the current release details.

You do not need to import the file again for later releases. Obtainium cannot
discover a configuration file merely because it is attached to a release; the
first download and import is manual. If the repository was already added to
Obtainium without a variant filter, remove that old entry before importing to
avoid a duplicate unfiltered entry.

The file removes the APK selection prompt. Fully unattended installation still
depends on Obtainium's installation method and Android permissions.

The import always lists every variant in `variants.yml`, including when a
manual workflow builds only a subset. Publish `all` variants at least once so
each imported entry has a release APK available.

## Android signing key

Every APK must be signed with the same key for Android to accept future updates.
The build requires these repository secrets:

- `ANDROID_SIGNING_KEYSTORE_BASE64`: the base64-encoded PKCS#12 keystore.
- `ANDROID_SIGNING_PASSWORD`: the password for the keystore and its `iceraven`
  key alias.

### Generate the key without installing anything

The included GitHub Actions workflow generates the key entirely on a GitHub
runner. You only need a browser:

1. Open the repository on GitHub and go to **Settings → Secrets and variables →
   Actions → New repository secret**.
2. Create `ANDROID_SIGNING_PASSWORD` with a unique, randomly generated password
   of at least 32 characters. Do not use words or a reused password. Save it in
   a password manager too. For example, this command generates exactly 32
   random characters without Java:

   ```sh
   openssl rand -base64 24
   ```
3. Open **Actions → Generate Android signing key → Run workflow**.
4. When it finishes, download the `iceraven-signing-key` artifact. It expires
   after one day.
5. Keep `iceraven-signing.p12` in a secure offline backup and keep its password
   in your password manager. GitHub does not let you download a secret after
   storing it.
6. Open `iceraven-signing.p12.base64` from the artifact and copy its complete
   single line into a new repository secret named
   `ANDROID_SIGNING_KEYSTORE_BASE64`.
7. Delete the key-generation workflow run and its artifact, then run the normal
   build workflow.

The PKCS#12 file in the short-lived artifact is encrypted with
`ANDROID_SIGNING_PASSWORD`. Because this is a public repository, other GitHub
users may be able to download that artifact until it is deleted or expires.
The 32-character random password protects the private key, but you should still
delete the workflow run immediately after making the offline backup.

Never replace either signing secret after distributing an APK. If the secrets
are lost, restore the original keystore and password from the offline backup;
generating another key makes existing installations impossible to update.

APKs produced before persistent signing was added used a different temporary
key on every run. They cannot be updated by the first persistent-key build.
Sync or export important browser data, uninstall each old app once, and install
the new APK. Updates made after that will install normally.

## Manual builds

Run the `Build IceRaven APKs` workflow from GitHub Actions. It always runs,
even when the latest upstream tag was already built.

Inputs:

- `upstream_ref`: use `latest-release`, a tag, branch, or commit.
- `variants`: use `all` or a comma-separated list like `personal,work`.

Successful builds upload the APKs and `obtainium.json`, then publish them to one
GitHub Release named like `IceRaven 2.45.0`.

## Daily upstream check

The `Daily upstream IceRaven check` workflow runs every day at 13:00 UTC. It
checks the latest IceRaven release tag and builds only when the tag differs from
`latest-upstream-tag.txt` stored on the separate `state` branch.

The workflow also has a manual `force_rebuild` input for testing the scheduled
path without waiting for a new upstream tag.
