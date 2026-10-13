#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -m)" != x86_64 ]]; then
  echo 'Build this Intel app using an x86_64 Python on an Intel Mac.' >&2
  exit 1
fi
python3 -m venv .macos-build-env
.macos-build-env/bin/python -m pip install -r macos/requirements-build.txt
.macos-build-env/bin/python - <<'ICON'
from PIL import Image
image = Image.open('static/favicon.png').convert('RGBA')
image.resize((1024, 1024), Image.Resampling.LANCZOS).save('macos/OverMesh.icns')
ICON
.macos-build-env/bin/python -m PyInstaller --noconfirm --distpath dist --workpath build/macos macos/OverMesh.spec
printf 'App ready: %s/dist/OverMesh.app\n' "$PWD"
