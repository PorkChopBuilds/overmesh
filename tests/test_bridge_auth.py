"""EST-82 B2: the automation bridge must work with a login enabled.

`_auth_gate` (app.py:before_request) runs before every /api/ route, so a valid
bridge bearer token still got 401 the moment auth was enabled — the documented
Home Assistant bridge broke. /api/bridge/send authenticates itself
(bridge._authorized) and is now exempt from the session gate; nothing else is.

The url_map walk guards the exemption list so a future route cannot silently
become reachable without a session.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

_TEST_DIR = tempfile.TemporaryDirectory(prefix="overmesh-bridge-auth-test-")
_TEST_ROOT = Path(_TEST_DIR.name)
_CONFIG_PATH = _TEST_ROOT / "config.json"
_DATA_DIR = _TEST_ROOT / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_PATH.write_text(
    json.dumps({
        "nodes": [], "mc_nodes": [], "app": {}, "gps": {}, "silent_mode": False,
        "bridge": {
            "webhooks": {"enabled": False, "urls": []},
            "ingest": {"enabled": True, "token": "sekret"},
        },
    }),
    encoding="utf-8",
)
os.environ.setdefault("OVERMESH_CONFIG", str(_CONFIG_PATH))
os.environ.setdefault("OVERMESH_DATA_DIR", str(_DATA_DIR))

import app as app_module  # noqa: E402
from config import CONFIG  # noqa: E402
from db import get_auth_setting, init_prefs_db, set_auth_setting  # noqa: E402

_TOKEN = {"Authorization": "Bearer sekret"}


class BridgeAuthGateTests(unittest.TestCase):
    def setUp(self):
        init_prefs_db()
        self.client = app_module.app.test_client()
        self._prev_auth = get_auth_setting("auth_enabled", "0")
        self._cfg_backup = json.loads(json.dumps(CONFIG))
        CONFIG["bridge"] = {
            "webhooks": {"enabled": False, "urls": []},
            "ingest": {"enabled": True, "token": "sekret"},
        }
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        set_auth_setting("auth_enabled", self._prev_auth)
        CONFIG.clear()
        CONFIG.update(self._cfg_backup)

    def _auth_on(self):
        set_auth_setting("auth_enabled", "1")

    def _auth_off(self):
        set_auth_setting("auth_enabled", "0")

    def test_login_on_valid_token_reaches_the_route(self):
        self._auth_on()
        resp = self.client.post("/api/bridge/send", json={"network": "mt", "text": "hi"},
                                headers=_TOKEN)
        # No radio is connected in this test => the bridge route itself answers
        # 503. The point is that the session gate no longer answers 401 first.
        self.assertEqual(resp.status_code, 503, resp.get_data(as_text=True))

    def test_login_on_missing_token_is_401_from_the_bridge(self):
        self._auth_on()
        resp = self.client.post("/api/bridge/send", json={"network": "mt", "text": "hi"})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"], "Unauthorized")

    def test_login_on_wrong_token_is_401(self):
        self._auth_on()
        resp = self.client.post("/api/bridge/send", json={"network": "mt", "text": "hi"},
                                headers={"Authorization": "Bearer nope"})
        self.assertEqual(resp.status_code, 401)

    def test_login_off_bridge_still_works(self):
        self._auth_off()
        resp = self.client.post("/api/bridge/send", json={"network": "mt", "text": "hi"},
                                headers=_TOKEN)
        self.assertEqual(resp.status_code, 503)

    def test_login_on_protected_route_still_requires_session(self):
        self._auth_on()
        resp = self.client.get("/api/silent_mode")
        self.assertEqual(resp.status_code, 401)

    def test_only_intended_exemptions_bypass_the_gate(self):
        exempt_api = []
        exempt_other = set()
        for rule in app_module.app.url_map.iter_rules():
            path = rule.rule
            if not app_module._auth_exempt(path):
                continue
            if path.startswith("/api/"):
                exempt_api.append(path)
            elif not path.startswith("/static"):
                exempt_other.add(path)
        self.assertEqual(sorted(exempt_api), ["/api/bridge/send"])
        self.assertEqual(exempt_other, {"/login", "/logout"})

    def test_unauthenticated_api_gets_are_all_blocked(self):
        self._auth_on()
        failures = []
        checked = 0
        for rule in app_module.app.url_map.iter_rules():
            path = rule.rule
            if not path.startswith("/api/") or app_module._auth_exempt(path):
                continue
            if "GET" not in (rule.methods or set()):
                continue
            url = re.sub(r"<[^>]+>", "1", path)
            checked += 1
            status = self.client.get(url).status_code
            if status != 401:
                failures.append((path, status))
        self.assertGreater(checked, 0, "the walk must actually exercise routes")
        self.assertEqual(failures, [], "routes reachable without a session")

    def test_every_non_exempt_route_is_blocked_for_every_method(self):
        """EST-85 sweep: the walk above only tried GET. Exercise every method the
        url_map advertises so a future POST/PATCH route can't slip past the gate."""
        self._auth_on()
        failures = []
        checked = 0
        for rule in app_module.app.url_map.iter_rules():
            path = rule.rule
            if app_module._auth_exempt(path):
                continue
            url = re.sub(r"<[^>]+>", "1", path)
            for method in sorted((rule.methods or set()) - {"OPTIONS", "HEAD"}):
                checked += 1
                resp = self.client.open(url, method=method)
                if method == "GET" and not path.startswith("/api/") and not path.startswith("/sse"):
                    ok = resp.status_code in (301, 302) and "/login" in (resp.headers.get("Location") or "")
                else:
                    ok = resp.status_code == 401
                if not ok:
                    failures.append((method, path, resp.status_code))
        self.assertGreater(checked, 100, "the walk must actually exercise routes")
        self.assertEqual(failures, [], "routes reachable without a session")


if __name__ == "__main__":
    unittest.main()
