import pytest
import asyncio
import os
import httpx
from typing import Dict, Any, Callable
from unittest.mock import patch, MagicMock, AsyncMock

class ChaosInjector:
    """Injects comprehensive failures into AIOS subsystems."""

    def __init__(self, sim_flags: Dict[str, Any]):
        self.sim_flags = sim_flags
        self.patches = []

    def __enter__(self):
        if not self.sim_flags:
            return self
        
        has_network = any(k.startswith("chaos_network_") for k in self.sim_flags)
        has_fs = any(k.startswith("chaos_fs_") for k in self.sim_flags)
        has_sys = any(k.startswith("chaos_sys_") for k in self.sim_flags)

        if has_network:
            self._apply_network_chaos()
        if has_fs:
            self._apply_filesystem_chaos()
        if has_sys:
            self._apply_system_chaos()
            
        self._apply_runtime_chaos()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for p in self.patches:
            p.stop()

    def _apply_runtime_chaos(self):
        async def crash_worker(*args, **kwargs):
            raise RuntimeError("Chaos: Worker crashed")
        async def crash_looper(*args, **kwargs):
            raise RuntimeError("Chaos: Looper crashed")
        async def crash_watcher(*args, **kwargs):
            raise RuntimeError("Chaos: Watcher crashed")
        async def crash_surveillance(*args, **kwargs):
            raise RuntimeError("Chaos: Surveillance crashed")

        if self.sim_flags.get("chaos_worker_crash"):
            p1 = patch("runtimes.competitive.CompetitiveRuntime._run_worker_x", side_effect=crash_worker)
            self.patches.append(p1)
            p1.start()
        if self.sim_flags.get("chaos_looper_crash"):
            p2 = patch("runtimes.competitive.CompetitiveRuntime._run_looper_y", side_effect=crash_looper)
            self.patches.append(p2)
            p2.start()
        if self.sim_flags.get("chaos_watcher_crash"):
            p3 = patch("runtimes.competitive.CompetitiveRuntime._run_watching_agent", side_effect=crash_watcher)
            self.patches.append(p3)
            p3.start()
        if self.sim_flags.get("chaos_surveillance_crash"):
            p4 = patch("runtimes.standard.StandardRuntime._run_surveillance_trace", side_effect=crash_surveillance)
            self.patches.append(p4)
            p4.start()

    def _apply_network_chaos(self):
        # httpx.AsyncClient.post mock
        original_post = httpx.AsyncClient.post

        async def mocked_post(client, url, *args, **kwargs):
            if self.sim_flags.get("chaos_network_timeout"):
                raise asyncio.TimeoutError("Chaos: Network Timeout")
            if self.sim_flags.get("chaos_network_disconnect"):
                raise httpx.ConnectError("Chaos: Connection Reset by Peer")
            if self.sim_flags.get("chaos_network_dns"):
                raise httpx.ConnectError("Chaos: DNS lookup failed")
            if self.sim_flags.get("chaos_network_ssl"):
                raise httpx.ConnectError("Chaos: SSL Handshake Failed")
            if self.sim_flags.get("chaos_network_latency"):
                await asyncio.sleep(self.sim_flags.get("latency_ms", 100) / 1000.0)
                class LatencyResponse:
                    status_code = 200
                    text = "Latency OK"
                    def json(self):
                        return {"choices": [{"message": {"content": "Latency OK"}}]}
                return LatencyResponse()

            if self.sim_flags.get("chaos_network_429"):
                return MagicMock(status_code=429, text="Too Many Requests")
            if self.sim_flags.get("chaos_network_500"):
                return MagicMock(status_code=500, text="Internal Server Error")
            if self.sim_flags.get("chaos_network_malformed"):
                return MagicMock(status_code=200, json=lambda: {"broken": "response", "missing_choices": True})
            if self.sim_flags.get("chaos_network_corrupt_json"):
                class CorruptResponse:
                    status_code = 200
                    text = "{ corrupted json"
                    def json(self):
                        import json
                        return json.loads(self.text)
                return CorruptResponse()

            return await original_post(client, url, *args, **kwargs)

        p = patch("httpx.AsyncClient.post", new=mocked_post)
        self.patches.append(p)
        p.start()

    def _apply_filesystem_chaos(self):
        original_open = open
        original_aio_open = None
        try:
            import aiofiles
            original_aio_open = aiofiles.open
        except ImportError:
            pass

        def mocked_open(file, mode="r", *args, **kwargs):
            if self.sim_flags.get("chaos_fs_permission_denied"):
                raise PermissionError(f"Chaos: Permission denied: {file}")
            if self.sim_flags.get("chaos_fs_disk_full") and "w" in mode:
                raise OSError(28, "Chaos: No space left on device")
            if self.sim_flags.get("chaos_fs_write_fail") and "w" in mode:
                raise IOError("Chaos: Disk I/O Write Failure")
            
            # Simulated corruption on read
            if self.sim_flags.get("chaos_fs_corrupt_checkpoint") and "r" in mode and "checkpoint" in str(file).lower():
                import io
                return io.StringIO("{ corrupted checkpoint data ]")

            return original_open(file, mode, *args, **kwargs)

        p1 = patch("builtins.open", side_effect=mocked_open)
        self.patches.append(p1)
        p1.start()

    def _apply_system_chaos(self):
        original_sleep = asyncio.sleep
        
        async def mocked_sleep(delay, result=None):
            if self.sim_flags.get("chaos_sys_memory_exhaustion"):
                raise MemoryError("Chaos: Out of Memory")
                
            # Delay multiplier
            if self.sim_flags.get("chaos_sys_slow_eventbus") and delay < 1.0:
                delay = delay * 50  # Slow things down massively
            
            return await original_sleep(delay, result)

        p_sleep = patch("asyncio.sleep", side_effect=mocked_sleep)
        self.patches.append(p_sleep)
        p_sleep.start()

        if self.sim_flags.get("chaos_sys_cancelled_task"):
            async def mocked_execute(*args, **kwargs):
                raise asyncio.CancelledError("Chaos: Task forcibly cancelled")
            p_wait = patch("runtimes.micro.MicroRuntime.execute", side_effect=mocked_execute)
            self.patches.append(p_wait)
            p_wait.start()
        
        if self.sim_flags.get("chaos_sys_queue_overflow"):
            async def mocked_put(*args, **kwargs):
                raise asyncio.QueueFull("Chaos: Queue Overflow")
            p_queue = patch("asyncio.PriorityQueue.put", side_effect=mocked_put)
            self.patches.append(p_queue)
            p_queue.start()
