"""EST-82 B4: OM Lite Log -> Import must use the same JSON contract as app.js.

lite.js sent a multipart file upload while /api/toc/import only reads JSON, so
Import failed every time. Lite now reads the file and POSTs
`{filename, content}` exactly like app.js tocImportFile — no second multipart
format on the route.

The test reads the exact body shape out of lite.js and posts that same body to
the real route, so the two ends are checked together.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

_TEST_DIR = tempfile.TemporaryDirectory(prefix="overmesh-toc-lite-test-")
_TEST_ROOT = Path(_TEST_DIR.name)
_CONFIG_PATH = _TEST_ROOT / "config.json"
_DATA_DIR = _TEST_ROOT / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_PATH.write_text(
    json.dumps({"nodes": [], "mc_nodes": [], "gps": {}, "silent_mode": False}),
    encoding="utf-8",
)
os.environ.setdefault("OVERMESH_CONFIG", str(_CONFIG_PATH))
os.environ.setdefault("OVERMESH_DATA_DIR", str(_DATA_DIR))

import db  # noqa: E402
from routes import toc as toc_routes  # noqa: E402

_LITE_JS = Path(_REPO, "static", "js", "lite.js").read_text(encoding="utf-8")


def _function_body(name):
    match = re.search(r"function %s\([^)]*\) \{.*?\n\}" % re.escape(name), _LITE_JS, re.S)
    if not match:
        raise AssertionError(f"{name}() not found in lite.js")
    return match.group(0)


class LiteTocImportBodyTests(unittest.TestCase):
    def test_lite_reads_the_file_and_sends_json(self):
        body = _function_body("importLog")
        self.assertNotIn("FormData", body, "Lite must not upload multipart")
        self.assertNotIn(".append('file'", body, "Lite must not append a multipart file")
        self.assertIn("file.text()", body, "Lite must read the file contents")
        self.assertIn("JSON.stringify({filename: file.name, content})", body,
                      "Lite must POST the same {filename, content} body as app.js")
        self.assertIn("application/json", body, "Lite must send the JSON content type")
        self.assertIn("/api/toc/import", body)

    def test_server_accepts_the_exact_lite_body(self):
        app = Flask(__name__)
        app.register_blueprint(toc_routes.bp)
        client = app.test_client()
        db.init_prefs_db()
        with db.get_prefs_db() as conn:
            conn.execute("DELETE FROM toc_log")

        txt = "[2026-10-10 12:00:00] [NOTE]\nhello entry\n"
        # Exactly what lite.js sends: JSON.stringify({filename: file.name, content}).
        body = {"filename": "toc.txt", "content": txt}
        resp = client.post("/api/toc/import", json=body)

        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["imported"], 1)


if __name__ == "__main__":
    unittest.main()
