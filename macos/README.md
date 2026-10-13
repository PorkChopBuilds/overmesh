# OverMesh for Intel Mac — Joker edition

Unzip the download, move OverMesh.app to Applications, and double-click it. Python and all dependencies are bundled; no Terminal or Pinokio is required. The app opens its localhost dashboard in your default browser.

This build replaces the embedded Cocoa/PyWebView window with a browser launcher to avoid that window-initialization crash path. A second click reopens the running dashboard. Use the power button at the top right to restart or shut down OverMesh. Closing the browser tab leaves the radio service running.

The Joker palette uses purple #AB5DEE, lilac #BE80FF, green #1DDD33, deep green #1DA11F, and neutral #C5C5C5. Existing settings are preserved; the requested purple accent is applied once. Later accent choices in Settings persist.

Add Meshtastic or MeshCore radios in Settings. Radio hardware communication is not yet verified. Data, history, settings, and logs live in ~/Library/Application Support/OverMesh and survive app replacement.

The dashboard binds only to localhost on an available port. This packaged app cannot use the source-code Git updater; replace it with a newer Mac build.

Built and backend-tested on Intel macOS 26.7.1. Packaged startup, duplicate launch, restart, shutdown, static assets, settings, serial-port discovery, and 37 focused upstream tests passed. The dashboard was visually checked in a browser. Full Finder-to-default-browser launching still requires user verification.

This is an ad-hoc-signed community build, not Apple-notarized. If macOS blocks a downloaded copy, use System Settings → Privacy & Security → Open Anyway after reviewing its source. Do not disable Gatekeeper globally.

## Rebuild

On an Intel Mac with Python 3.13 and Apple's command-line tools, run ./macos/build.sh. The build produces dist/OverMesh.app. Dependencies are pinned in macos/requirements-build.txt.

An isolated backend test:

```
OVERMESH_DESKTOP_DATA=/tmp/overmesh-test dist/OverMesh.app/Contents/MacOS/OverMesh --backend-test
```

Use --no-browser for a supervised test server. Tests should always use a temporary OVERMESH_DESKTOP_DATA directory, never live radio data.

Source baseline: PorkChopBuilds/overmesh commit 04f8b92e924603129f63bbd605b8b27e245225a9. Upstream MIT license included.
