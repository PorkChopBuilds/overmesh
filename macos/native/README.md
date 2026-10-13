# OverMesh Desktop — Intel Mac beta

A separate Swift/AppKit application with its own WebKit window, Dock icon, native Edit menu, and Command-Q. The bundled radio service runs as a child process. Closing the last window or quitting stops that service. No external browser opens for the dashboard.

## Install

Unzip the download and move **OverMesh Desktop.app** to Applications. Shut down the browser edition using its dashboard power button before opening Desktop. Both editions use `~/Library/Application Support/OverMesh` so settings, radios, history, and the Joker theme carry over. They must not run simultaneously against the same radio data.

The browser release remains available. This is an ad-hoc-signed community beta, not an Apple-notarized build. Radio hardware testing is still required.

## Behavior

- Starts the dashboard on a free localhost port and shows it inside the app.
- Restarts the backend and reloads its new local address when Restart is selected.
- Stops the child service when you quit; also stops if the parent application unexpectedly exits.
- Keeps external web links in your default browser.
- Reports startup failures in a native dialog instead of silently disappearing.
- Logs are `OverMesh.log` and `Desktop-launcher.log` in the data folder.

## Build

On an Intel Mac with Python 3.13 and Apple developer tools:

```
bash macos/build.sh
python3 macos/package_native.py dist/OverMesh.app 'dist/OverMesh Desktop.app'
```

To test the actual native window with empty temporary data:

```
OVERMESH_TEST_DIR=/tmp/overmesh-native-test python3 macos/native/verify_window.py 'dist/OverMesh Desktop.app'
```

The test checks that WebKit renders the dashboard with the purple accent, captures a screenshot, closes the window, and verifies that the backend stops. It must run in a graphical macOS login session; a restricted shell that cannot register applications with WindowServer cannot perform this GUI test.
