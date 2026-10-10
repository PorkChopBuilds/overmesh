"""EST-82 B7: /api/mesh/sense/passive must honour its input, and Lite must sync.

The server ignored {"enabled": bool} and just flipped state, so OM Lite (which
starts at senseOn=false and posts its desired value) turned passive capture OFF
on the first tap even though the server had it ON. The endpoint now sets the
requested value (via helpers._as_bool) and only falls back to toggling when the
body omits "enabled"; Lite syncs S.senseOn from /api/mesh/sense/status on load
and adopts the server's answer after each toggle.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flask import Flask

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

_TEST_DIR = tempfile.TemporaryDirectory(prefix="overmesh-sense-passive-test-")
_TEST_ROOT = Path(_TEST_DIR.name)
_CONFIG_PATH = _TEST_ROOT / "config.json"
_DATA_DIR = _TEST_ROOT / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_PATH.write_text(
    json.dumps({"nodes": [], "mc_nodes": [], "app": {}, "gps": {}, "silent_mode": False}),
    encoding="utf-8",
)
os.environ.setdefault("OVERMESH_CONFIG", str(_CONFIG_PATH))
os.environ.setdefault("OVERMESH_DATA_DIR", str(_DATA_DIR))

from config import CONFIG  # noqa: E402
from routes import sense as sense_routes  # noqa: E402

_LITE_JS = Path(_REPO, "static", "js", "lite.js").read_text(encoding="utf-8")


def _function_body(name):
    match = re.search(r"function %s\([^)]*\) \{.*?\n\}" % re.escape(name), _LITE_JS, re.S)
    if not match:
        raise AssertionError(f"{name}() not found in lite.js")
    return match.group(0)


class SensePassiveServerTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(sense_routes.bp)
        self.client = self.app.test_client()
        self._backup = json.loads(json.dumps(CONFIG))
        CONFIG.clear()
        CONFIG.update({"nodes": [], "mc_nodes": [], "app": {}, "gps": {}, "silent_mode": False})
        self._passive_backup = sense_routes._sense_state.get("passive")
        sense_routes._sense_state["passive"] = False
        self.save_mock = mock.patch.object(sense_routes, "save_config").start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        mock.patch.stopall()
        CONFIG.clear()
        CONFIG.update(self._backup)
        sense_routes._sense_state["passive"] = self._passive_backup

    def _post(self, payload):
        return self.client.post("/api/mesh/sense/passive", json=payload)

    def test_enabled_true_sets_true(self):
        resp = self._post({"enabled": True})
        self.assertEqual(resp.status_code, 200)
        self.assertIs(resp.get_json()["passive"], True)
        self.assertIs(sense_routes._sense_state["passive"], True)

    def test_enabled_true_is_idempotent(self):
        self._post({"enabled": True})
        resp = self._post({"enabled": True})
        self.assertIs(resp.get_json()["passive"], True,
                      "a second enabled=true must not toggle it back off")
        self.assertIs(CONFIG["sense_passive"], True)

    def test_enabled_false_sets_false(self):
        sense_routes._sense_state["passive"] = True
        resp = self._post({"enabled": False})
        self.assertIs(resp.get_json()["passive"], False)

    def test_enabled_string_false_sets_false(self):
        sense_routes._sense_state["passive"] = True
        resp = self._post({"enabled": "false"})
        self.assertIs(resp.get_json()["passive"], False)

    def test_missing_enabled_keeps_legacy_toggle(self):
        first = self._post({})
        self.assertIs(first.get_json()["passive"], True)
        second = self._post({})
        self.assertIs(second.get_json()["passive"], False)


class LiteSenseSyncTests(unittest.TestCase):
    def test_toggle_sends_enabled_and_uses_server_answer(self):
        body = _function_body("toggleSense")
        self.assertNotIn("S.senseOn = !S.senseOn", body,
                         "Lite must not flip locally and hope the server agrees")
        self.assertIn("enabled:", body, "Lite must send its desired state")
        self.assertIn("d.passive", body, "Lite must adopt the server's answer")
        self.assertIn("/api/mesh/sense/passive", body)

    def test_load_syncs_from_status(self):
        sync = _function_body("syncSenseOn")
        self.assertIn("/api/mesh/sense/status", sync)
        self.assertIn("passive", sync)
        self.assertIn("S.senseOn", sync)
        init = _function_body("init")
        self.assertIn("syncSenseOn", init, "init() must sync Sense state on load")


if __name__ == "__main__":
    unittest.main()
