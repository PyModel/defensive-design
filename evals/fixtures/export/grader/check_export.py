"""Behavioral acceptance checks. Do not expose to the implementation agent."""
from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from pathlib import Path


TARGET = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("export", TARGET / "export.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load export fixture")
export = importlib.util.module_from_spec(spec)
sys.modules["export"] = export
spec.loader.exec_module(export)


class Authz:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def check(self, context, document_id):
        self.calls.append((context, document_id))
        answer = next(self.answers)
        if isinstance(answer, BaseException):
            raise answer
        return answer


class Stream(io.BytesIO):
    def __init__(self, data=b"payload", read_error=None, close_error=None, chunk=3):
        super().__init__(data)
        self.read_error = read_error
        self.close_error = close_error
        self.close_called = False
        self.chunk = chunk
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        if size < 0 or size > 4097:
            raise AssertionError("unbounded read")
        if self.read_error:
            raise self.read_error
        return super().read(min(size, self.chunk))

    def close(self):
        self.close_called = True
        super().close()
        if self.close_error:
            raise self.close_error


class Storage:
    def __init__(self, stream=None, publish_error=None):
        self.stream = stream if stream is not None else Stream()
        self.publish_error = publish_error
        self.open_calls = []
        self.publish_calls = []

    def open_document(self, tenant, document_id):
        self.open_calls.append((tenant, document_id))
        return self.stream

    def publish(self, tenant, principal, document_id, content):
        self.publish_calls.append((tenant, principal, document_id, content))
        if self.publish_error:
            raise self.publish_error
        return "export-reference"


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.context = export.Context("tenant_A", "principal_1")

    def invoke(self, authz, storage, document_id="doc_1"):
        return export.export_document(self.context, document_id, authz, storage)

    def test_success_keeps_scope_rechecks_and_closes(self):
        authz = Authz([True, True])
        storage = Storage()
        result = self.invoke(authz, storage)
        self.assertEqual(result, "export-reference")
        self.assertEqual(storage.open_calls, [("tenant_A", "doc_1")])
        self.assertEqual(storage.publish_calls, [("tenant_A", "principal_1", "doc_1", b"payload")])
        self.assertEqual(len(authz.calls), 2)
        self.assertTrue(storage.stream.close_called)

    def test_denied_or_unavailable_auth_does_not_open_or_publish(self):
        for answer, expected in ((False, PermissionError), (TimeoutError("unavailable"), TimeoutError),
                                 (RuntimeError("unexpected"), RuntimeError)):
            with self.subTest(answer=type(answer).__name__):
                storage = Storage()
                with self.assertRaises(expected):
                    self.invoke(Authz([answer]), storage)
                self.assertEqual(storage.open_calls, [])
                self.assertEqual(storage.publish_calls, [])

    def test_revocation_or_timeout_before_publish_closes_without_publication(self):
        for answer, expected in ((False, PermissionError), (TimeoutError("unavailable"), TimeoutError)):
            with self.subTest(answer=type(answer).__name__):
                storage = Storage()
                with self.assertRaises(expected):
                    self.invoke(Authz([True, answer]), storage)
                self.assertTrue(storage.stream.close_called)
                self.assertEqual(storage.publish_calls, [])

    def test_invalid_document_ids_never_cross_a_boundary(self):
        for identifier in (None, "", "../doc", "x" * 65, "doc\n", "dóc", 17):
            with self.subTest(identifier=identifier):
                authz = Authz([True, True])
                storage = Storage()
                with self.assertRaises(ValueError):
                    self.invoke(authz, storage, identifier)
                self.assertEqual(authz.calls, [])
                self.assertEqual(storage.open_calls, [])

    def test_size_limit_and_short_reads(self):
        for size, succeeds in ((0, True), (4096, True), (4097, False)):
            with self.subTest(size=size):
                storage = Storage(Stream(b"a" * size, chunk=31))
                if succeeds:
                    self.invoke(Authz([True, True]), storage)
                    self.assertEqual(storage.publish_calls[0][-1], b"a" * size)
                else:
                    with self.assertRaises(ValueError):
                        self.invoke(Authz([True, True]), storage)
                    self.assertEqual(storage.publish_calls, [])
                self.assertTrue(storage.stream.close_called)
                self.assertTrue(all(0 < n <= 4097 for n in storage.stream.read_sizes))

    def test_read_and_cleanup_failures_preserve_primary_error(self):
        primary = OSError("read failed")
        storage = Storage(Stream(read_error=primary, close_error=RuntimeError("cleanup failed")))
        with self.assertRaises(OSError) as caught:
            self.invoke(Authz([True, True]), storage)
        self.assertIs(caught.exception, primary)
        self.assertTrue(storage.stream.close_called)
        self.assertEqual(storage.publish_calls, [])

    def test_cleanup_failure_alone_propagates(self):
        storage = Storage(Stream(close_error=RuntimeError("cleanup failed")))
        with self.assertRaises(RuntimeError):
            self.invoke(Authz([True, True]), storage)
        self.assertTrue(storage.stream.close_called)
        self.assertEqual(len(storage.publish_calls), 1)

    def test_ambiguous_publish_is_not_retried_and_stream_closes(self):
        storage = Storage(publish_error=TimeoutError("ambiguous"))
        with self.assertRaises(TimeoutError):
            self.invoke(Authz([True, True]), storage)
        self.assertEqual(len(storage.publish_calls), 1)
        self.assertTrue(storage.stream.close_called)


if __name__ == "__main__":
    unittest.main()
