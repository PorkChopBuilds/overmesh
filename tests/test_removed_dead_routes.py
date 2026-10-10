"""EST-82 H2: three dead routes were removed.

/api/system/restart and /api/system/shutdown (settings.py) and
/api/radio/<id>/announce (radio.py) had no caller in app.js, lite.js, the
templates, tests or docs — the UI uses app.py's /api/restart and /api/shutdown
instead. They also shelled out with a hardcoded XDG_RUNTIME_DIR.

This guards both ends: the URL rules are gone from the url_map, no source
mentions the handlers, and the live restart/shutdown routes are untouched.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

_TEST_DIR = tempfile.TemporaryDirectory(prefix="overmesh-dead-routes-test-")
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

import app as app_module  # noqa: E402

_REMOVED_RULES = (
    "/api/system/restart",
    "/api/system/shutdown",
    "/api/radio/<radio_id>/announce",
)
_REMOVED_HANDLERS = ("api_system_restart", "api_system_shutdown", "api_radio_announce")


class RemovedDeadRouteTests(unittest.TestCase):
    def test_removed_rules_are_absent(self):
        rules = {rule.rule for rule in app_module.app.url_map.iter_rules()}
        still_present = sorted(set(_REMOVED_RULES) & rules)
        self.assertEqual(still_present, [], "dead routes still registered in the url_map")

    def test_removed_handlers_are_absent_from_source(self):
        bad = []
        for rel in ("routes/settings.py", "routes/radio.py"):
            text = Path(_REPO, rel).read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), 1):
                if any(name in line for name in _REMOVED_HANDLERS):
                    bad.append(f"{rel}:{lineno}: {line.strip()}")
        self.assertEqual(bad, [])

    def test_live_restart_and_shutdown_routes_remain(self):
        rules = {rule.rule for rule in app_module.app.url_map.iter_rules()}
        self.assertIn("/api/restart", rules)
        self.assertIn("/api/shutdown", rules)


if __name__ == "__main__":
    unittest.main()
