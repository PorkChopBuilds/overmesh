from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata
root = Path(SPECPATH).parent
hidden = collect_submodules('meshtastic') + collect_submodules('meshcore') + collect_submodules('bleak.backends.corebluetooth') + collect_submodules('serial.tools')
data = [(str(root / name), name) for name in ('templates', 'static')]
data += [(str(root / name), '.') for name in ('VERSION', 'LICENSE', 'config.example.json')]
data += collect_data_files('meshcore')
for package in ('meshtastic', 'meshcore', 'pyserial', 'pypubsub'):
    data += copy_metadata(package)
a = Analysis([str(root / 'macos/desktop.py')], pathex=[str(root)], binaries=[], datas=data, hiddenimports=hidden, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['pytest', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='OverMesh', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False, target_arch='x86_64', codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='OverMesh')
app = BUNDLE(coll, name='OverMesh.app', icon=str(root / 'macos/OverMesh.icns'), bundle_identifier='com.porkchopbuilds.overmesh', version='2.0.2', info_plist={'NSHighResolutionCapable': True, 'LSUIElement': True, 'NSBluetoothAlwaysUsageDescription': 'OverMesh connects to your mesh radios over Bluetooth.', 'NSBluetoothPeripheralUsageDescription': 'OverMesh connects to your mesh radios over Bluetooth.', 'NSLocalNetworkUsageDescription': 'OverMesh connects to mesh radios on your local network.', 'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True, 'NSAllowsArbitraryLoads': True}, 'LSMinimumSystemVersion': '13.0'})
