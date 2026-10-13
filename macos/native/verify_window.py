"""Run the actual AppKit + WebKit window using isolated, radio-free data."""
import json, os, pathlib, subprocess, sys
bundle=pathlib.Path(sys.argv[1]).resolve()
data=pathlib.Path(os.environ['OVERMESH_TEST_DIR']).resolve();data.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,OVERMESH_DESKTOP_DATA=str(data))
subprocess.run([str(bundle/'Contents/MacOS/OverMeshDesktop'),'--smoke-test'],env=env,check=True,timeout=90)
result=json.loads((data/'native-smoke.json').read_text())
assert result['ok'],result
assert result['page']['accent'].lower()=='#ab5dee',result
assert not (data/'desktop-status.json').exists(),'Quit left the backend running'
print(json.dumps(result,indent=2))
