"""EST-83 client-side guards.

The app has no browser test harness, so the contract these fixes are about
lives in the source strings/wiring of static/js/app.js and the two templates.
Each guard below reads the *real* source and asserts the exact wiring the fix
introduced. They are deliberately narrow: a guard that does not pin the
failure mode is not a guard (see the EST-83 report / the team's "a check that
can't fail isn't a check" rule).

Red-first: every method here was run against the pre-fix source and failed,
then passed after the fix, in the same commit.
"""
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static/js/app.js"
INDEX = ROOT / "templates/index.html"


def _js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _html() -> str:
    return INDEX.read_text(encoding="utf-8")


def _fn_body(src: str, name: str) -> str:
    """Return the braces-balanced body of `function name(...)`.

    Only used on small handlers; the corpus is ordinary JS (balanced braces in
    template-literal ${} interpolations included), so a depth scan is enough.
    """
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", src)
    if not m:
        raise AssertionError(f"function {name}() not found")
    start = src.index("{", m.end())
    depth = 0
    for i in range(start, len(src)):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(f"unbalanced braces in {name}()")


class TestRequestFailureFeedback(unittest.TestCase):
    """B5/B9/B10/B11: a failed request must be visible and must not lose input."""

    def setUp(self):
        self.src = _js()

    def test_b11_chat_send_shows_json_error_not_raw_body(self):
        body = _fn_body(self.src, "sendChat")
        self.assertNotIn("throw new Error(await r.text())", body,
                         "B11: the raw response body must not be shown as the alert")
        self.assertRegex(body, r"\.json\(\)", "B11: the error body must be parsed as JSON")
        self.assertRegex(body, r"\.error\b", "B11: the parsed error text must be used")

    def test_b10_map_dm_restores_input_and_alerts_on_failure(self):
        body = _fn_body(self.src, "sendMapDM")
        self.assertIn("input.value = text", body,
                      "B10: a failed map-DM send must restore the typed text")
        self.assertIn("showAlert", body, "B10: a failed map-DM send must alert")

    def test_b9_mc_ignore_checks_ok_and_alerts(self):
        body = _fn_body(self.src, "ignoreMcContact")
        self.assertRegex(body, r"r\.ok", "B9: ignoreMcContact must check r.ok before mutating")
        self.assertIn("showAlert", body, "B9: a failed ignore must alert")

    def test_b9_mt_ignore_checks_ok_and_alerts(self):
        body = _fn_body(self.src, "ignoreNode")
        self.assertRegex(body, r"r\.ok", "B9: ignoreNode must check r.ok")
        self.assertIn("showAlert", body, "B9: a failed ignore must alert")

    def test_b5_sense_reads_429_json_and_starts_cooldown(self):
        body = _fn_body(self.src, "triggerSense")
        self.assertRegex(body, r"r\.status\s*===\s*429",
                         "B5: a 429 (server-side cooldown) must be read, not thrown")
        self.assertIn("senseCooldownTick(d.cooldown_remaining)", body,
                      "B5: the cooldown message + ticker must run on 429")


if __name__ == "__main__":
    unittest.main()
