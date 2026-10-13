import subprocess,os,json,time,pathlib,urllib.request
base=pathlib.Path.cwd();data=pathlib.Path(os.environ['OVERMESH_TEST_DIR']);data.mkdir(parents=True,exist_ok=True)
exe=base/'dist/OverMesh.app/Contents/MacOS/OverMesh'
env=dict(os.environ,OVERMESH_DESKTOP_DATA=str(data))
p=subprocess.Popen([str(exe),'--no-browser'],env=env)
def ready(old=None):
    for _ in range(100):
        try:
            status=json.loads((data/'desktop-status.json').read_text());url=status['url']
            if url!=old:
                with urllib.request.urlopen(url,timeout=1) as r:
                    assert r.status==200
                    return url
        except (OSError,ValueError):pass
        time.sleep(.1)
    raise AssertionError('Startup timed out')
try:
    url=ready()
    result=subprocess.run([str(exe),'--no-browser'],env=env,timeout=15)
    assert result.returncode==0 and p.poll() is None
    req=urllib.request.Request(url+'/api/restart',method='POST')
    assert json.load(urllib.request.urlopen(req))['ok']
    new=ready(url)
    assert p.poll() is None
    req=urllib.request.Request(new+'/api/shutdown',method='POST')
    assert json.load(urllib.request.urlopen(req))['ok']
    assert p.wait(timeout=15)==0
    print('PASS: packaged startup, duplicate launch, restart, shutdown')
finally:
    if p.poll() is None:p.terminate();p.wait(timeout=15)
