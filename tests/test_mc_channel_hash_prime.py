import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

_TEST_DIR = tempfile.TemporaryDirectory(prefix="overmesh-test-")
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
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import mesh_mc  # noqa: E402


class _Event:
    def __init__(self, type, payload=None):
        self.type = type
        self.payload = {} if payload is None else payload


class _FakeCommands:
    """A device whose channel list is read after connect.

    ``channels`` maps a slot index to the CHANNEL_INFO payload the device returns.
    Any slot not present, and every slot past the last populated one, answers ERROR
    (which is exactly how a real radio reports the end of its channel list).
    ``fail_at`` raises on that slot, ``hang_at`` never answers (times out) on it.
    """

    def __init__(self, channels=None, fail_at=None, hang_at=None):
        self.channels = channels or {}
        self.fail_at = fail_at
        self.hang_at = hang_at
        self.channel_reads = []

    async def set_time(self, ts):
        return _Event(mesh_mc.EventType.OK)

    async def send_appstart(self):
        return _Event(mesh_mc.EventType.SELF_INFO, {
            "public_key": "aa" * 32,
            "manual_add_contacts": False,
        })

    async def send_device_query(self):
        return _Event(mesh_mc.EventType.DEVICE_INFO, {
            "max_channels": 8,
            "max_contacts": 100,
        })

    async def get_contacts(self):
        return _Event(mesh_mc.EventType.CONTACTS, {"bb" * 32: {"public_key": "bb" * 32}})

    async def get_channel(self, idx):
        self.channel_reads.append(idx)
        if self.hang_at is not None and idx == self.hang_at:
            await asyncio.sleep(30)
        if self.fail_at is not None and idx == self.fail_at:
            raise RuntimeError("channel read failed")
        payload = self.channels.get(idx)
        if payload is None:
            return _Event(mesh_mc.EventType.ERROR, {})
        return _Event(mesh_mc.EventType.CHANNEL_INFO, {"channel_idx": idx, **payload})


class _FakeMc:
    def __init__(self, commands):
        self.commands = commands


def _close_bg(coro, label=""):
    """Stand-in for _mc_bg_task: the connect flow's background coroutines would
    otherwise outlive the test; close them so nothing is left un-awaited."""
    try:
        coro.close()
    except Exception:
        pass
    return None


class McChannelHashPrimeOnConnectTests(unittest.TestCase):
    """EST-85 R1: the hash cache must be primed by the connect itself.

    The cache was only filled when a browser fetched /api/mc/<id>/channels, so a
    headless instance (no browser open, restarted on every update) scored relayed
    channel traffic on timing alone.
    """

    def setUp(self):
        self.cid = "mcprime"
        self._saved_connections = dict(mesh_mc.mc_connections)
        mesh_mc._mc_channel_hashes.pop(self.cid, None)
        with mesh_mc.mc_connections_lock:
            mesh_mc.mc_connections[self.cid] = {
                "mc": None, "status": "disconnected", "config": {},
            }

    def tearDown(self):
        with mesh_mc.mc_connections_lock:
            mesh_mc.mc_connections.clear()
            mesh_mc.mc_connections.update(self._saved_connections)
        mesh_mc._mc_channel_hashes.pop(self.cid, None)

    def _run_connect(self, commands):
        node_cfg = {
            "id": self.cid,
            "name": "FakeMC",
            "type": "tcp",
            "host": "127.0.0.1",
            "tcp_port": 4403,
            # "" skips the path-hash-mode write, which is not what this test covers
            "path_hash_mode": "",
        }
        mc = _FakeMc(commands)

        async def _fake_create(*args, **kwargs):
            return mc

        async def _go():
            with mock.patch.object(mesh_mc, "_create_meshcore", _fake_create), \
                 mock.patch.object(mesh_mc, "_subscribe_mc_events", lambda *a, **k: None), \
                 mock.patch.object(mesh_mc, "push_to_sse", lambda *a, **k: None), \
                 mock.patch.object(mesh_mc, "_mc_bg_task", _close_bg), \
                 mock.patch.object(mesh_mc, "init_mc_msgs_db", lambda *a, **k: None), \
                 mock.patch.object(mesh_mc, "register_mc_msgs_db", lambda *a, **k: None), \
                 mock.patch.object(mesh_mc, "register_mc_passive_db", lambda *a, **k: None), \
                 mock.patch.object(mesh_mc, "_mc_archive_merge_contacts", lambda *a, **k: None):
                await mesh_mc._connect_mc_node_async(node_cfg)
            with mesh_mc.mc_connections_lock:
                return mesh_mc.mc_connections.get(self.cid, {}).get("status")

        return asyncio.run(_go())

    def test_connect_primes_the_channel_hash_cache(self):
        commands = _FakeCommands(channels={
            0: {"channel_name": "Ops", "channel_hash": "ab"},
            1: {"channel_name": "Public", "channel_hash": "cd"},
        })
        status = self._run_connect(commands)
        self.assertEqual(status, "connected")
        self.assertEqual(mesh_mc._mc_channel_hash_for(self.cid, 0), "ab")
        self.assertEqual(mesh_mc._mc_channel_hash_for(self.cid, 1), "cd")
        # The read must stop at the end of the list, not keep probing slots.
        self.assertEqual(commands.channel_reads, [0, 1, 2])

    def test_failing_channel_read_does_not_break_connect(self):
        # Slot 0 answers, slot 1 raises: the connect must still complete and the
        # hashes read before the failure must still be cached.
        commands = _FakeCommands(
            channels={0: {"channel_name": "Ops", "channel_hash": "ab"}},
            fail_at=1,
        )
        status = self._run_connect(commands)
        self.assertEqual(status, "connected")
        self.assertEqual(mesh_mc._mc_channel_hash_for(self.cid, 0), "ab")

    def test_hanging_channel_read_is_bounded_and_does_not_break_connect(self):
        # A radio that never answers a slot read must not stall the connect: the
        # whole connect coroutine runs under a 120 s timeout (connect_mc_node).
        commands = _FakeCommands(channels={0: {"channel_hash": "ab"}}, hang_at=1)
        started = time.monotonic()
        with mock.patch.object(mesh_mc, "MC_CHANNEL_HASH_PRIME_BUDGET_S", 0.3):
            status = self._run_connect(commands)
        elapsed = time.monotonic() - started
        self.assertEqual(status, "connected")
        self.assertLess(elapsed, 5.0, "channel-hash prime exceeded its budget")


if __name__ == "__main__":
    unittest.main()
