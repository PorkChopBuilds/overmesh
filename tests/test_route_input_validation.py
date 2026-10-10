"""EST-82 B8: malformed input to two mutating routes must be a clean 400.

* /api/mc/<radio>/passive_obs/cleanup parsed ttl_days outside its try (bad input
  -> an opaque 500 HTML page) and did not clamp it (ttl_days=-1 deleted
  everything newer than a future cutoff).
* /api/mc/contact/<id>/notes stored whatever it was given, so a dict crashed
  sqlite with a 500.

Both are now validated: ttl_days must parse to an int >= 1; notes must be a
string (a dict is serialised with json.dumps).
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flask import Flask

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

_TEST_DIR = tempfile.TemporaryDirectory(prefix="overmesh-route-input-test-")
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

from routes import mc as mc_routes  # noqa: E402
from routes import nodes as nodes_routes  # noqa: E402


class McPassiveObsCleanupValidationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(mc_routes.bp)
        self.client = self.app.test_client()
        self.cleanup = mock.patch.object(
            mc_routes, "cleanup_passive_obs", return_value=3
        ).start()
        self.addCleanup(mock.patch.stopall)

    def _post(self, payload):
        return self.client.post("/api/mc/mc_1/passive_obs/cleanup", json=payload)

    def test_non_numeric_ttl_is_400_not_500(self):
        resp = self._post({"ttl_days": "abc"})
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        self.assertIn("ttl_days", resp.get_json()["error"])
        self.cleanup.assert_not_called()

    def test_negative_ttl_is_rejected(self):
        resp = self._post({"ttl_days": -1})
        self.assertEqual(resp.status_code, 400)
        self.cleanup.assert_not_called()

    def test_zero_ttl_is_rejected(self):
        resp = self._post({"ttl_days": 0})
        self.assertEqual(resp.status_code, 400)
        self.cleanup.assert_not_called()

    def test_default_ttl_is_30(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 200)
        self.cleanup.assert_called_once_with("mc_1", ttl_days=30)

    def test_valid_ttl_passes_through(self):
        resp = self._post({"ttl_days": 7})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["deleted"], 3)
        self.cleanup.assert_called_once_with("mc_1", ttl_days=7)


class McContactNotesValidationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(nodes_routes.bp)
        self.client = self.app.test_client()
        self.set_note = mock.patch.object(nodes_routes, "set_mc_note").start()
        self.addCleanup(mock.patch.stopall)

    def _patch(self, payload):
        return self.client.patch("/api/mc/contact/abc/notes", json=payload)

    def test_string_is_stored(self):
        resp = self._patch({"notes": "hello"})
        self.assertEqual(resp.status_code, 200)
        self.set_note.assert_called_once_with("abc", "hello")

    def test_dict_is_json_dumped(self):
        resp = self._patch({"notes": {"a": 1}})
        self.assertEqual(resp.status_code, 200)
        self.set_note.assert_called_once_with("abc", json.dumps({"a": 1}))

    def test_list_is_400_not_500(self):
        resp = self._patch({"notes": [1, 2]})
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        self.set_note.assert_not_called()

    def test_number_is_400_not_500(self):
        resp = self._patch({"notes": 5})
        self.assertEqual(resp.status_code, 400)
        self.set_note.assert_not_called()

    def test_missing_notes_defaults_to_empty_object(self):
        resp = self._patch({})
        self.assertEqual(resp.status_code, 200)
        self.set_note.assert_called_once_with("abc", "{}")


if __name__ == "__main__":
    unittest.main()
