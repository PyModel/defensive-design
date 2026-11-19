"""Local contract checks for document export; no external providers are used."""
import contextlib
import io
import unittest

from export import Context, export_document


class Stream:
    def __init__(self, events, data=b"document", chunk_size=4097):
        self.events = events
        self.data = data
        self.chunk_size = chunk_size
        self.position = 0
        self.requests = []
        self.close_calls = 0
        self.read_error = None
        self.close_error = None

    def read(self, size=-1):
        if size < 1 or size > 4097:
            raise AssertionError("read must use a positive bounded size")
        self.events.append("read")
        self.requests.append(size)
        if self.read_error is not None:
            raise self.read_error
        end = min(self.position + size, self.position + self.chunk_size, len(self.data))
        chunk = self.data[self.position:end]
        self.position = end
        return chunk

    def close(self):
        self.events.append("close")
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class Authz:
    def __init__(self, events, outcomes=(True, True)):
        self.events = events
        self.outcomes = iter(outcomes)
        self.calls = []

    def check(self, context, document_id):
        self.events.append("check")
        self.calls.append((context, document_id))
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class Storage:
    def __init__(self, events, stream):
        self.events = events
        self.stream = stream
        self.opens = []
        self.publishes = []
        self.open_error = None
        self.publish_error = None

    def open_document(self, tenant_id, document_id):
        self.events.append("open")
        self.opens.append((tenant_id, document_id))
        if self.open_error is not None:
            raise self.open_error
        return self.stream

    def publish(self, tenant_id, principal_id, document_id, content):
        self.events.append("publish")
        self.publishes.append((tenant_id, principal_id, document_id, content))
        if self.publish_error is not None:
            raise self.publish_error
        return "export-reference"


class ExportDocumentTests(unittest.TestCase):
    def setUp(self):
        self.context = Context("authenticated-tenant", "authenticated-principal")
        self.events = []
        self.stream = Stream(self.events)
        self.authz = Authz(self.events)
        self.storage = Storage(self.events, self.stream)

    def run_export(self, document_id="Document_123-valid"):
        return export_document(self.context, document_id, self.authz, self.storage)

    def test_invalid_ids_rejected_before_dependencies(self):
        invalid = ["", "a" * 65, "../document", "a/b", "a\\b", "a.b", "a b",
                   "a\n", "a\r", "a\x00", "é", "Ａ", "١", None, 42, b"doc"]
        for document_id in invalid:
            with self.subTest(document_id=document_id):
                with self.assertRaises(ValueError):
                    self.run_export(document_id)
                self.assertEqual(self.events, [])

    def test_valid_id_boundaries_and_character_set(self):
        for document_id in ["a", "Z", "0", "_", "-", "a" * 64,
                            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"]:
            with self.subTest(document_id=document_id):
                self.setUp()
                self.assertEqual(self.run_export(document_id), "export-reference")
                self.assertEqual(self.storage.opens, [(self.context.tenant_id, document_id)])
                self.assertEqual(self.storage.publishes[0][:3],
                                 (self.context.tenant_id, self.context.principal_id, document_id))
                self.assertEqual(self.authz.calls, [(self.context, document_id)] * 2)
                self.assertEqual(self.stream.close_calls, 1)

    def test_denial_prevents_open(self):
        self.authz = Authz(self.events, [False])
        with self.assertRaises(PermissionError):
            self.run_export()
        self.assertEqual(self.events, ["check"])

    def test_authorization_unavailability_prevents_open(self):
        for error_type in [TimeoutError, OSError, RuntimeError]:
            with self.subTest(error_type=error_type.__name__):
                self.setUp()
                error = error_type("authorization unavailable")
                self.authz = Authz(self.events, [error])
                with self.assertRaises(error_type) as raised:
                    self.run_export()
                self.assertIs(raised.exception, error)
                self.assertEqual(self.events, ["check"])

    def test_empty_and_limit_sized_documents(self):
        for size in [0, 1, 4095, 4096]:
            with self.subTest(size=size):
                self.setUp()
                self.stream.data = b"x" * size
                self.assertEqual(self.run_export(), "export-reference")
                self.assertEqual(self.storage.publishes[0][3], self.stream.data)
                self.assertIsInstance(self.storage.publishes[0][3], bytes)
                self.assertEqual(self.stream.close_calls, 1)

    def test_short_reads_are_not_eof(self):
        self.stream.data = bytes(range(256)) * 16
        self.stream.chunk_size = 3
        self.run_export()
        self.assertEqual(self.storage.publishes[0][3], self.stream.data)
        self.assertEqual(self.stream.position, 4096)
        self.assertEqual(self.stream.requests[-1], 1)
        self.assertEqual(self.events[-3:], ["check", "publish", "close"])

    def test_oversized_documents_stop_after_one_extra_byte(self):
        for size, chunk_size in [(4097, 4097), (100000, 1), (100000, 73)]:
            with self.subTest(size=size, chunk_size=chunk_size):
                self.setUp()
                self.stream.data = b"x" * size
                self.stream.chunk_size = chunk_size
                with self.assertRaises(ValueError):
                    self.run_export()
                self.assertEqual(self.stream.position, 4097)
                self.assertLessEqual(len(self.stream.requests), 4097)
                self.assertEqual(len(self.authz.calls), 1)
                self.assertEqual(self.storage.publishes, [])
                self.assertEqual(self.stream.close_calls, 1)

    def test_authorization_revoked_during_read_blocks_publish(self):
        self.authz = Authz(self.events, [True, False])
        with self.assertRaises(PermissionError):
            self.run_export()
        self.assertEqual(self.stream.position, len(self.stream.data))
        self.assertEqual(self.storage.publishes, [])
        self.assertEqual(self.events[-2:], ["check", "close"])
        self.assertEqual(self.stream.close_calls, 1)

    def test_final_authorization_outage_blocks_publish(self):
        for error_type in [TimeoutError, OSError, RuntimeError]:
            with self.subTest(error_type=error_type.__name__):
                self.setUp()
                error = error_type("authorization unavailable")
                self.authz = Authz(self.events, [True, error])
                with self.assertRaises(error_type) as raised:
                    self.run_export()
                self.assertIs(raised.exception, error)
                self.assertEqual(self.storage.publishes, [])
                self.assertEqual(self.stream.close_calls, 1)

    def test_storage_open_error_propagates(self):
        error = OSError("open failed")
        self.storage.open_error = error
        with self.assertRaises(OSError) as raised:
            self.run_export()
        self.assertIs(raised.exception, error)
        self.assertEqual(self.events, ["check", "open"])
        self.assertEqual(self.stream.close_calls, 0)

    def test_read_error_propagates_and_closes(self):
        error = OSError("read failed")
        self.stream.read_error = error
        with self.assertRaises(OSError) as raised:
            self.run_export()
        self.assertIs(raised.exception, error)
        self.assertEqual(self.storage.publishes, [])
        self.assertEqual(self.stream.close_calls, 1)

    def test_possibly_committed_publish_is_not_retried(self):
        error = TimeoutError("publish outcome unknown")
        self.storage.publish_error = error
        with self.assertRaises(TimeoutError) as raised:
            self.run_export()
        self.assertIs(raised.exception, error)
        self.assertEqual(len(self.storage.publishes), 1)
        self.assertEqual(self.stream.close_calls, 1)

    def test_cleanup_failure_alone_propagates(self):
        error = OSError("close failed")
        self.stream.close_error = error
        with self.assertRaises(OSError) as raised:
            self.run_export()
        self.assertIs(raised.exception, error)
        self.assertEqual(len(self.storage.publishes), 1)
        self.assertEqual(self.stream.close_calls, 1)

    def test_cleanup_failure_does_not_mask_primary_errors(self):
        for stage in ["read", "authz", "denied", "publish", "oversized", "interrupted"]:
            with self.subTest(stage=stage):
                self.setUp()
                primary = KeyboardInterrupt() if stage == "interrupted" else RuntimeError("primary")
                cleanup = OSError("private-cleanup-detail-canary")
                self.stream.close_error = cleanup
                expected_type = type(primary)
                if stage in ["read", "interrupted"]:
                    self.stream.read_error = primary
                elif stage == "authz":
                    self.authz = Authz(self.events, [True, primary])
                elif stage == "denied":
                    self.authz = Authz(self.events, [True, False])
                    expected_type = PermissionError
                elif stage == "publish":
                    self.storage.publish_error = primary
                else:
                    self.stream.data = b"x" * 4097
                    expected_type = ValueError
                with self.assertRaises(expected_type) as raised:
                    self.run_export()
                if stage not in ["denied", "oversized"]:
                    self.assertIs(raised.exception, primary)
                notes = getattr(raised.exception, "__notes__", [])
                self.assertTrue(raised.exception.__cause__ is cleanup or notes)
                self.assertNotIn("private-cleanup-detail-canary", " ".join(notes))
                self.assertEqual(self.stream.close_calls, 1)
                self.assertEqual(len(self.storage.publishes), int(stage == "publish"))

    def test_base_exception_still_closes(self):
        error = KeyboardInterrupt()
        self.stream.read_error = error
        with self.assertRaises(KeyboardInterrupt) as raised:
            self.run_export()
        self.assertIs(raised.exception, error)
        self.assertEqual(self.stream.close_calls, 1)

    def test_provider_errors_and_contents_are_not_printed_or_logged(self):
        self.stream.data = b"private-document-canary"
        self.storage.publish_error = RuntimeError("private-provider-error-canary")
        self.stream.close_error = OSError("private-cleanup-error-canary")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertNoLogs():
                with self.assertRaises(RuntimeError):
                    self.run_export()
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
