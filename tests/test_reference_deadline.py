"""Regression tests for cooperative deadlines completing without yielding.

The clock advances inside synchronous work. No real sleeps or live network are
needed, and patches are restored before returning to the test runner.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

import httpx

from scripts import verify_reference as harness


class DeadlineCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def fetch_with_parse_duration(self, elapsed: float):
        loop = asyncio.get_running_loop()
        clock = [loop.time()]
        original = harness.mod._parse_profile

        def parse(body, user_id):
            clock[0] += elapsed
            return original(body, user_id)

        async def handler(request):
            return httpx.Response(200, json={"display_name": "Alice"})

        with (
            patch.object(loop, "time", side_effect=lambda: clock[0]),
            patch.object(harness.mod, "_parse_profile", side_effect=parse),
        ):
            return await harness.run_fetch(handler, config=harness.cfg(deadline_s=1.0))

    async def test_success_before_deadline_is_preserved(self):
        result = await self.fetch_with_parse_duration(0.5)
        self.assertIs(result.status, harness.mod.FetchStatus.SUCCESS)
        self.assertIsNotNone(result.data)

    async def test_synchronous_parse_crossing_deadline_is_not_success(self):
        result = await self.fetch_with_parse_duration(2.0)
        self.assertIs(result.status, harness.mod.FetchStatus.CANCELLED)
        self.assertEqual(result.error_code, "DEADLINE_EXCEEDED")
        self.assertIsNone(result.data)

    async def test_completion_at_deadline_is_expired(self):
        result = await self.fetch_with_parse_duration(1.0)
        self.assertIs(result.status, harness.mod.FetchStatus.CANCELLED)
        self.assertEqual(result.error_code, "DEADLINE_EXCEEDED")

    async def test_response_cleanup_crossing_deadline_is_not_success(self):
        loop = asyncio.get_running_loop()
        clock = [loop.time()]
        closed = []

        class SlowClose(harness.AsyncBytes):
            async def aclose(self):
                closed.append(True)
                clock[0] += 2.0

        async def handler(request):
            return httpx.Response(200, stream=SlowClose(b'{"display_name":"Alice"}'))

        with patch.object(loop, "time", side_effect=lambda: clock[0]):
            result = await harness.run_fetch(handler, config=harness.cfg(deadline_s=1.0))
        self.assertTrue(closed)
        self.assertIs(result.status, harness.mod.FetchStatus.CANCELLED)
        self.assertIsNone(result.data)


if __name__ == "__main__":
    unittest.main()
