"""Click-to-open Mac app: bundled local server, dashboard in the default browser."""
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.request

from flask import jsonify
from werkzeug.serving import make_server

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT))


def open_dashboard(url):
    subprocess.run(['/usr/bin/open', url], check=True)


def main():
    os.umask(0o077)
    data = Path(os.environ.get('OVERMESH_DESKTOP_DATA', Path.home() / 'Library/Application Support/OverMesh'))
    data.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(data / 'OverMesh.log', maxBytes=2_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.info('Desktop build 2.0.2 starting; executable=%s', sys.executable)
    lock = (data / 'desktop.lock').open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if '--native-desktop' in sys.argv:
            raise SystemExit(73)
        # A second click opens the running dashboard instead of silently exiting.
        for _ in range(50):
            try:
                status = json.loads((data / 'desktop-status.json').read_text())
                url = status['url']
                if not url.startswith('http://127.0.0.1:'):
                    raise ValueError('Unexpected dashboard URL')
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        if '--no-browser' not in sys.argv:
                            open_dashboard(url)
                        return
            except (OSError, ValueError, KeyError):
                time.sleep(0.2)
        raise RuntimeError('An existing OverMesh instance is not responding. Quit it and reopen.')
    config = data / 'config.json'
    if not config.exists():
        config.write_bytes((ROOT / 'config.example.json').read_bytes())
    saved = json.loads(config.read_text())
    prefs = saved.setdefault('app', {})
    if prefs.get('desktop_theme') != 'joker-v1':
        prefs.update(accent_color='#ab5dee', desktop_theme='joker-v1')
        temporary = config.with_suffix('.tmp')
        temporary.write_text(json.dumps(saved, indent=2))
        temporary.replace(config)
    os.environ['OVERMESH_CONFIG'] = str(config)
    os.environ['OVERMESH_DATA_DIR'] = str(data)
    os.environ['OVERMESH_HOST'] = '127.0.0.1'
    import app
    import routes.settings as settings
    settings.update_check_loop = lambda: None
    app.app.view_functions['settings.api_settings_update_available'] = lambda: jsonify(available=False)
    app.app.view_functions['settings.api_settings_update_run'] = lambda: (jsonify(error='Replace OverMesh.app with a newer Mac build to update. Your settings are kept.'), 409)
    server = make_server('127.0.0.1', 0, app.app, threaded=True)
    url = f'http://127.0.0.1:{server.server_port}'
    stop = threading.Event()
    restart = threading.Event()

    def shutdown():
        threading.Timer(0.4, stop.set).start()
        return jsonify(ok=True)

    def restart_app():
        restart.set()
        return shutdown()

    app.app.view_functions['api_shutdown'] = shutdown
    app.app.view_functions['api_restart'] = restart_app
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    parent_pid = int(os.environ.get('OVERMESH_PARENT_PID', '0'))
    if parent_pid:
        def monitor_parent():
            while not stop.wait(1):
                if os.getppid() != parent_pid:
                    stop.set()
                    return
        threading.Thread(target=monitor_parent, daemon=True).start()
    app.startup()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (data / 'desktop-status.json').write_text(json.dumps({'pid': os.getpid(), 'url': url, 'native_token': os.environ.get('OVERMESH_NATIVE_TOKEN', '')}))
    logging.info('OverMesh dashboard ready at %s', url)
    try:
        if '--backend-test' in sys.argv:
            results = {}
            for route in ('/', '/static/js/app.js', '/static/css/app.css', '/api/settings/app', '/api/settings/ports'):
                with urllib.request.urlopen(url + route, timeout=15) as response:
                    body = response.read()
                    assert response.status == 200 and body, route
                    if route.endswith('app.css'):
                        assert b'#ab5dee' in body and b'#1ddd33' in body
                    results[route] = {'status': response.status, 'bytes': len(body)}
            (data / 'backend-result.json').write_text(json.dumps(results, indent=2))
        else:
            if '--no-browser' not in sys.argv:
                open_dashboard(url)
            stop.wait()
    finally:
        server.shutdown()
        server.server_close()
        app.disconnect_all_mc()
        from state import connections, connections_lock
        with connections_lock:
            interfaces = [value.get('iface') for value in connections.values()]
        for interface in interfaces:
            if interface:
                try:
                    interface.close()
                except Exception:
                    logging.exception('Could not close radio')
        (data / 'desktop-status.json').unlink(missing_ok=True)
        lock.close()
    if restart.is_set():
        args = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).resolve())]
        args += [arg for arg in sys.argv[1:] if arg in ('--no-browser', '--native-desktop')]
        os.execv(sys.executable, args)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.exception('OverMesh startup failed')
        if '--backend-test' not in sys.argv and '--no-browser' not in sys.argv:
            # Show a useful error without importing the failing Cocoa bridge.
            subprocess.run(['/usr/bin/osascript', '-e', 'display alert "OverMesh could not start" message "See Library/Application Support/OverMesh/OverMesh.log for details."'])
        raise
