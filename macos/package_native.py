"""Assemble a Swift AppKit host around the separately frozen radio service."""
import pathlib, plistlib, subprocess, sys
root = pathlib.Path(__file__).resolve().parent.parent
backend = pathlib.Path(sys.argv[1]).resolve()
dest = pathlib.Path(sys.argv[2]).resolve()
if dest.exists():
    raise SystemExit('Output already exists; select a fresh build directory.')
macos = dest / 'Contents/MacOS'
resources = dest / 'Contents/Resources'
macos.mkdir(parents=True); resources.mkdir()
cache = root / 'build/swift-cache'; cache.mkdir(parents=True, exist_ok=True)
subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(cache), '-O', '-target', 'x86_64-apple-macos13.0', '-framework', 'Cocoa', '-framework', 'WebKit', str(root/'macos/native/main.swift'), '-o', str(macos/'OverMeshDesktop')], check=True)
subprocess.run(['ditto', str(backend), str(resources/'Backend.app')], check=True)
subprocess.run(['ditto', str(root/'macos/OverMesh.icns'), str(resources/'OverMesh.icns')], check=True)
info = dict(CFBundleName='OverMesh Desktop', CFBundleDisplayName='OverMesh Desktop', CFBundleExecutable='OverMeshDesktop', CFBundleIdentifier='com.porkchopbuilds.overmesh.desktop', CFBundlePackageType='APPL', CFBundleShortVersionString='2.1.0', CFBundleVersion='1', CFBundleIconFile='OverMesh.icns', NSHighResolutionCapable=True, LSMinimumSystemVersion='13.0', NSBluetoothAlwaysUsageDescription='OverMesh connects to your mesh radios.', NSLocalNetworkUsageDescription='OverMesh connects to your mesh radios on the local network.', NSAppTransportSecurity={'NSAllowsLocalNetworking':True,'NSAllowsArbitraryLoads':True})
with (dest/'Contents/Info.plist').open('wb') as f: plistlib.dump(info,f)
subprocess.run(['codesign','--force','--sign','-',str(dest)],check=True)
subprocess.run(['codesign','--verify','--deep','--strict',str(dest)],check=True)
print(dest)
