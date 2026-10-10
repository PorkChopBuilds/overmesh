import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

_TEST_DIR = tempfile.TemporaryDirectory(prefix="overmesh-test-")
_TEST_ROOT = Path(_TEST_DIR.name)
_CONFIG_PATH = _TEST_ROOT / "config.json"
_DATA_DIR = _TEST_ROOT / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_PATH.write_text(json.dumps({"nodes": [], "mc_nodes": [], "gps": {}, "silent_mode": False}), encoding="utf-8")

os.environ.setdefault("OVERMESH_CONFIG", str(_CONFIG_PATH))
os.environ.setdefault("OVERMESH_DATA_DIR", str(_DATA_DIR))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import mesh_mc  # noqa: E402


def _rx(**kw):
    """A relayed, encrypted GRP_TXT RX log entry as the meshcore parser emits it.

    It carries the channel hash (first byte of the GRP_TXT payload) but no
    sender/timestamp/text, which live inside the encrypted payload.
    """
    rx = {
        "payload_typename": "GRP_TXT",
        "path_len": 2,
        "stored_at": 1000.0,
    }
    rx.update(kw)
    return rx


def _channel_msg(**kw):
    msg = {"subtype": "channel", "channel_idx": 0}
    msg.update(kw)
    return msg


class McRxConfidenceScoringTests(unittest.TestCase):
    """Relayed channel packets: channel-hash + timing evidence (EST-84 §2)."""

    def test_hash_and_tight_timing_is_high(self):
        msg = _channel_msg(channel_hash="ab")
        rx = _rx(chan_hash="ab", stored_at=1000.0)
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, rx, now_ts=1001.0), "high"
        )

    def test_hash_match_alone_is_medium(self):
        # RX arrived long before the message: same channel, but the pairing is
        # no longer pinned by timing.
        msg = _channel_msg(channel_hash="ab")
        rx = _rx(chan_hash="ab", stored_at=900.0)
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, rx, now_ts=1000.0), "medium"
        )

    def test_tight_timing_alone_is_medium(self):
        # No channel hash on the RX record (or no known hash for the channel):
        # only the timing window links it.
        msg = _channel_msg(channel_hash="ab")
        rx = _rx(chan_hash="cd", stored_at=1000.0)
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, rx, now_ts=1001.0), "medium"
        )

    def test_no_evidence_is_low(self):
        msg = _channel_msg(channel_hash="ab")
        rx = _rx(chan_hash="cd", stored_at=900.0)
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, rx, now_ts=1000.0), "low"
        )

    def test_missing_message_hash_is_not_a_match(self):
        msg = _channel_msg()  # no channel_hash derived
        rx = _rx(chan_hash="ab", stored_at=1000.0)
        # Timing alone -> medium; a missing expected hash must never count as a match.
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, rx, now_ts=1001.0), "medium"
        )

    def test_direct_packet_stays_medium(self):
        # path_len 0 is a direct reception; behaviour is deliberately unchanged.
        msg = _channel_msg(channel_hash="ab")
        rx = _rx(chan_hash="cd", stored_at=900.0, path_len=0)
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, rx, now_ts=1000.0), "medium"
        )

    def test_late_copy_is_never_high(self):
        # A copy attached after delivery is a post-hoc match: capped at medium.
        msg = _channel_msg(channel_hash="ab")
        rx = _rx(chan_hash="ab", stored_at=1000.0)
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, rx, late=True, now_ts=1001.0),
            "medium",
        )

    def test_dm_scoring_unchanged(self):
        msg = {"subtype": "dm", "pubkey_prefix": "aa" * 6}
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, {}, now_ts=1000.0), "high"
        )
        self.assertEqual(
            mesh_mc._rx_correlation_confidence(msg, {}, late=True, now_ts=1000.0),
            "medium",
        )


class McMessageBadgeTests(unittest.TestCase):
    """The message badge = the confidence of the copy whose path is shown (EST-84 §1)."""

    @staticmethod
    def _copy(path_len, confidence, path, rssi=-70):
        return {
            "path": path,
            "path_len": path_len,
            "path_hash_mode": 0,
            "path_hash_size": 1,
            "route_type": "FLOOD",
            "rx_rssi": rssi,
            "rx_snr": 5.0,
            "payload_type": "GRP_TXT",
            "first_seen": 1000.0,
            "confidence": confidence,
        }

    def test_badge_uses_shown_path_not_worst_copy(self):
        msg = {"subtype": "channel"}
        copies = [
            self._copy(1, "high", "aa", rssi=-50),
            self._copy(4, "low", "bb", rssi=-95),
        ]
        mesh_mc._apply_rx_copies_to_message(msg, copies)
        self.assertEqual(msg["path"], "aa")
        self.assertEqual(msg["rx_confidence"], "high")

    def test_badge_follows_shown_path_even_when_another_copy_is_higher(self):
        msg = {"subtype": "channel"}
        copies = [
            self._copy(1, "low", "aa", rssi=-95),
            self._copy(4, "high", "bb", rssi=-50),
        ]
        mesh_mc._apply_rx_copies_to_message(msg, copies)
        self.assertEqual(msg["path"], "aa")
        self.assertEqual(msg["rx_confidence"], "low")

    def test_unparseable_first_seen_does_not_break_the_message(self):
        # EST-85 sweep: the copy sort key cast first_seen with a bare float(),
        # while the sibling path_len/rssi ranks guarded. One malformed timestamp
        # raised ValueError out of the live message path. It must be treated like
        # a missing one (0.0) and the copy ordering must still hold.
        msg = {"subtype": "channel"}
        copies = [
            self._copy(2, "high", "aa"),
            {**self._copy(1, "low", "bb"), "first_seen": "not-a-number"},
        ]
        mesh_mc._apply_rx_copies_to_message(msg, copies)
        self.assertEqual(msg["path"], "bb")   # path_len still decides first
        self.assertEqual(msg["rx_confidence"], "low")


class McChannelHashCacheTests(unittest.TestCase):
    """The message side only carries channel_idx, so the expected hash is cached
    from device channel reads (get_channels/CHANNEL_INFO)."""

    def tearDown(self):
        mesh_mc._mc_channel_hashes.clear()

    def test_remembers_hash_from_channel_info(self):
        mesh_mc._remember_mc_channel_hashes("mc1", [
            {"channel_idx": 0, "channel_name": "Ops", "channel_hash": "Ab"},
            {"channel_idx": 2, "channel_name": "Public", "channel_hash": "cd"},
        ])
        self.assertEqual(mesh_mc._mc_channel_hash_for("mc1", 0), "ab")
        self.assertEqual(mesh_mc._mc_channel_hash_for("mc1", 2), "cd")
        self.assertEqual(mesh_mc._mc_channel_hash_for("mc1", 9), "")

    def test_derives_hash_from_secret_when_device_omits_it(self):
        # channel_hash = SHA256(channel_secret).hexdigest()[0:2], per the protocol
        # (meshcore reader.py derives CHANNEL_INFO's channel_hash exactly this way).
        import hashlib

        secret = bytes(range(16))
        expected = hashlib.sha256(secret).hexdigest()[0:2]
        self.assertEqual(mesh_mc._mc_channel_hash_from_secret(secret), expected)
        mesh_mc._remember_mc_channel_hashes("mc2", [
            {"channel_idx": 1, "channel_secret": secret},
        ])
        self.assertEqual(mesh_mc._mc_channel_hash_for("mc2", 1), expected)


class McRelayedChannelFlowTests(unittest.TestCase):
    """End-to-end through the real helpers: RX log -> best-recent-rx -> copy
    confidence -> message badge. Unit-green is not enough (EST-84)."""

    def setUp(self):
        mesh_mc._mc_recent_rx_logs.clear()
        mesh_mc._mc_channel_hashes.clear()

    def tearDown(self):
        mesh_mc._mc_recent_rx_logs.clear()
        mesh_mc._mc_channel_hashes.clear()

    def _flow(self, now_ts, chan_hash, stored_at):
        mesh_mc._remember_mc_channel_hashes("mc1", [
            {"channel_idx": 1, "channel_name": "Ops", "channel_hash": "ab"},
        ])
        mesh_mc._remember_rx_log("mc1", {
            "payload_typename": "GRP_TXT",
            "path_len": 3,
            "path": "aabbcc",
            "path_hash_size": 1,
            "rssi": -88,
            "snr": 4.0,
            "chan_hash": chan_hash,
            "stored_at": stored_at,
        })
        msg = {"subtype": "channel", "channel_idx": 1, "text": "hello"}
        rx = mesh_mc._best_recent_rx_for_message("mc1", "channel", now_ts, msg=msg)
        self.assertIsNotNone(rx)
        copy = mesh_mc._rx_copy_from_entry(msg, rx)
        copy["confidence"] = mesh_mc._rx_correlation_confidence(
            {**msg, "channel_hash": mesh_mc._mc_channel_hash_for("mc1", 1)},
            rx,
            now_ts=now_ts,
        )
        sse = {"subtype": "channel", "channel": 1}
        mesh_mc._apply_rx_copies_to_message(sse, [copy])
        return sse

    def test_relayed_packet_on_known_channel_is_reported_high(self):
        now_ts = time.time()
        sse = self._flow(now_ts, chan_hash="ab", stored_at=now_ts)
        self.assertEqual(sse["path"], "aabbcc")
        self.assertEqual(sse["rx_confidence"], "high")

        # A later, longer-path copy with weaker evidence must NOT drag the badge
        # down: the badge follows the copy whose path is shown ("aabbcc", high).
        late = {
            "path": "ddeeff00", "path_len": 4, "path_hash_mode": 0, "path_hash_size": 1,
            "route_type": "FLOOD", "rx_rssi": -100, "rx_snr": -2.0,
            "payload_type": "GRP_TXT", "first_seen": now_ts + 1.0, "confidence": "low",
        }
        mesh_mc._apply_rx_copies_to_message(sse, list(sse["rx_copies"]) + [late])
        self.assertEqual(sse["path"], "aabbcc")
        self.assertEqual(sse["rx_confidence"], "high")

    def test_stale_packet_on_a_different_channel_is_reported_low(self):
        now_ts = time.time()
        sse = self._flow(now_ts, chan_hash="cd", stored_at=now_ts - 30.0)
        self.assertEqual(sse["path"], "aabbcc")
        self.assertEqual(sse["rx_confidence"], "low")


if __name__ == "__main__":
    unittest.main()
