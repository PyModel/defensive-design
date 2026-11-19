"""Network-free regression tests for retries, process deadlines and evidence output."""
from __future__ import annotations

import errno
import io
import json
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import check_links as links

URL = "https://example.invalid/source"


class FetchTests(unittest.TestCase):
    def response(self, status: int) -> MagicMock:
        response = MagicMock()
        response.__enter__.return_value.status = status
        return response

    def test_success_closes_response(self) -> None:
        response = self.response(200)
        with patch.object(links.urllib.request, "urlopen", return_value=response) as opener:
            self.assertEqual(links.fetch_status(URL), 200)
        self.assertEqual(opener.call_count, 1)
        response.__exit__.assert_called_once()

    def test_permanent_http_failure_closes_body_without_retry(self) -> None:
        for code in (401, 403, 404, 410, 429, 501, 505):
            with self.subTest(code=code):
                body = io.BytesIO(b"unneeded")
                error = urllib.error.HTTPError(URL, code, "", Message(), body)
                with patch.object(links.urllib.request, "urlopen", side_effect=error) as opener:
                    self.assertEqual(links.fetch_status(URL), code)
                self.assertTrue(body.closed)
                self.assertEqual(opener.call_count, 1)

    def test_transient_failure_retries_with_jitter_and_closes_error(self) -> None:
        body = io.BytesIO()
        error = urllib.error.HTTPError(URL, 503, "", Message(), body)
        with (
            patch.object(links.urllib.request, "urlopen", side_effect=[error, self.response(200)]) as opener,
            patch.object(links.random, "uniform", return_value=0.125) as jitter,
            patch.object(links.time, "sleep") as sleep,
        ):
            self.assertEqual(links.fetch_status(URL), 200)
        self.assertEqual(opener.call_count, 2)
        self.assertTrue(body.closed)
        jitter.assert_called_once_with(0.0, 0.25)
        sleep.assert_called_once_with(0.125)

    def test_attempt_budget_is_strict(self) -> None:
        with (
            patch.object(links.urllib.request, "urlopen", side_effect=TimeoutError) as opener,
            patch.object(links.time, "sleep"),
        ):
            self.assertIsNone(links.fetch_status(URL))
        self.assertEqual(opener.call_count, 2)

    def test_retry_after_outside_budget_or_invalid_is_not_ignored(self) -> None:
        for header in ("30", "junk", "-1"):
            with self.subTest(header=header):
                headers = Message()
                headers["Retry-After"] = header
                error = urllib.error.HTTPError(URL, 503, "", headers, io.BytesIO())
                with patch.object(links.urllib.request, "urlopen", side_effect=error) as opener:
                    self.assertEqual(links.fetch_status(URL), 503)
                self.assertEqual(opener.call_count, 1)
        with patch.object(links.random, "uniform", return_value=0.1):
            self.assertAlmostEqual(links.retry_delay("1", 0, 2) or 0, 1.1)
            self.assertIsNone(links.retry_delay("1", 0, 0.5))

    def test_only_transient_network_failures_retry(self) -> None:
        for exc, transient in (
            (ssl.SSLCertVerificationError(), False),
            (urllib.error.URLError("unsupported protocol"), False),
            (socket.gaierror(socket.EAI_NONAME, "missing name"), False),
            (socket.gaierror(socket.EAI_AGAIN, "temporary DNS"), True),
            (OSError(errno.ECONNRESET, "reset"), True),
        ):
            with self.subTest(exc=exc):
                self.assertEqual(links.transient_error(urllib.error.URLError(exc)), transient)


class SweepTests(unittest.TestCase):
    def run_with_command(self, code: str, *, budget: float = 2, link_timeout: float = 1):
        processes: list[subprocess.Popen[bytes]] = []
        original = subprocess.Popen

        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process

        with (
            patch.object(links, "_worker_command", return_value=[sys.executable, "-c", code]),
            patch.object(links.subprocess, "Popen", side_effect=start),
        ):
            result = links.check_urls([URL + str(i) for i in range(3)], workers=2,
                                      budget=budget, link_timeout=link_timeout)
        self.assertTrue(all(process.poll() is not None for process in processes))
        self.assertTrue(all(process.stdout is not None and process.stdout.closed for process in processes))
        return result

    def test_completed_workers_keep_every_result(self) -> None:
        results = self.run_with_command('print(\'{"status":404}\')')
        self.assertEqual(len(results), 3)
        self.assertEqual({result.verdict for result in results}, {"broken"})

    def test_hung_workers_and_unstarted_urls_are_bounded_and_reaped(self) -> None:
        start = time.monotonic()
        results = self.run_with_command("import time; time.sleep(60)", budget=0.25, link_timeout=5)
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertEqual(len(results), 3)
        self.assertEqual({result.reason for result in results}, {"run_deadline"})
        self.assertEqual({result.verdict for result in results}, {"unverified"})

    def test_link_timeout_does_not_consume_whole_sweep_budget(self) -> None:
        results = self.run_with_command("import time; time.sleep(60)", budget=2, link_timeout=0.15)
        self.assertEqual({result.reason for result in results}, {"link_deadline"})

    def test_failed_or_malformed_worker_cannot_become_verified(self) -> None:
        for code in ('print("bad-json")', 'print(\'{"status":true}\')', "raise SystemExit(1)"):
            with self.subTest(code=code):
                self.assertEqual({result.reason for result in self.run_with_command(code)}, {"worker_error"})

    def test_invalid_budgets_and_inputs_start_no_workers(self) -> None:
        with patch.object(links.subprocess, "Popen") as start:
            for kwargs in ({"budget": float("nan")}, {"budget": 0}, {"link_timeout": 601},
                           {"workers": 0}, {"workers": 17}, {"workers": True}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    links.check_urls([URL], **kwargs)
            for urls in ([URL, URL], ["https://x/" + "a" * 4096], ["https://user:password@x/"],
                         ["https://x/\n"], ["http://x/"], ["https://x:65536/"],
                         [URL + str(i) for i in range(links.MAX_LINKS + 1)]):
                with self.subTest(urls=urls[:2]), self.assertRaises(ValueError):
                    links.check_urls(urls)
            start.assert_not_called()

    def test_start_failure_is_unverified(self) -> None:
        with patch.object(links.subprocess, "Popen", side_effect=OSError("process quota")):
            results = links.check_urls([URL])
        self.assertEqual(results[0].reason, "worker_start_failed")

    def test_keyboard_interrupt_cleans_up_running_workers(self) -> None:
        processes: list[subprocess.Popen[bytes]] = []
        original = subprocess.Popen

        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process

        with (
            patch.object(links, "_worker_command", return_value=[sys.executable, "-c", "import time; time.sleep(60)"]),
            patch.object(links.subprocess, "Popen", side_effect=start),
            patch.object(links.time, "sleep", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            links.check_urls([URL], workers=1)
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].poll())

    def test_json_distinguishes_unverified_from_broken_and_exit_status(self) -> None:
        results = [links.LinkResult(URL, None, "unverified", "run_deadline")]
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            with patch.object(links, "check_urls", return_value=results), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(links.main(["--json", str(report)]), 0)
            data = json.loads(report.read_text())
        self.assertEqual(data["counts"], {"ok": 0, "broken": 0, "unverified": 1})
        self.assertEqual(data["results"][0]["reason"], "run_deadline")
        with patch.object(links, "check_urls", return_value=[links.LinkResult(URL, 404, "broken", "http")]), \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(links.main([]), 1)


if __name__ == "__main__":
    unittest.main()
