"""Local standard-library regression checks for the exporter boundary contract."""
import contextlib
import io
import unittest

from export import Context, export_document


class TrackedStream:
    def __init__(self, content=b"", *, chunk_size=None, read_error=None,
                 fail_after_reads=0, close_error=None, events=None):
        self.content = content
        self.chunk_size = chunk_size
        self.read_error = read_error
        self.fail_after_reads = fail_after_reads
        self.close_error = close_error
        self.events = events if events is not None else []
        self.position = 0
        self.requests = []
        self.close_calls = 0

    def read(self, size):
        if not isinstance(size, int) or not 1 <= size <= 4097:
            raise AssertionError("read must have a positive bounded size")
        self.events.append("read")
        self.requests.append(size)
        if self.read_error is not None and len(self.requests) > self.fail_after_reads:
            raise self.read_error
        count = min(size, self.chunk_size) if self.chunk_size else size
        result = self.content[self.position:self.position + count]
        self.position += len(result)
        return result

    def close(self):
        self.events.append("close")
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error


class Authz:
    def __init__(self, decisions, events):
        self.decisions = list(decisions)
        self.calls = []
        self.events = events

    def check(self, context, document_id):
        self.events.append("authorize")
        self.calls.append((context, document_id))
        if not self.decisions:
            raise AssertionError("unexpected authorization retry")
        result = self.decisions.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class Storage:
    def __init__(self, stream, events, *, open_error=None, publish_error=None):
        self.stream = stream
        self.events = events
        self.open_error = open_error
        self.publish_error = publish_error
        self.open_calls = []
        self.publish_calls = []
        self.reference = "export-reference"

    def open_document(self, tenant_id, document_id):
        self.events.append("open")
        self.open_calls.append((tenant_id, document_id))
        if self.open_error is not None:
            raise self.open_error
        return self.stream

    def publish(self, tenant_id, principal_id, document_id, content):
        self.events.append("publish")
        self.publish_calls.append((tenant_id, principal_id, document_id, content))
        if self.publish_error is not None:
            raise self.publish_error
        return self.reference


class ExportTests(unittest.TestCase):
    context = Context("authenticated-tenant", "authenticated-principal")

    def fixture(self, content=b"content", *, decisions=(True, True),
                open_error=None, publish_error=None, **stream_options):
        events = []
        stream = TrackedStream(content, events=events, **stream_options)
        authz = Authz(decisions, events)
        storage = Storage(stream, events, open_error=open_error, publish_error=publish_error)
        return stream, authz, storage, events

    def test_invalid_ids_fail_before_any_external_call(self):
        invalid = ["", "a" * 65, ".", "..", "a/b", "a\\b", "a b", "a\n", "a\r",
                   "\ta", "a\x00", "é", "Ａ", "١", None, 12, b"valid"]
        for document_id in invalid:
            with self.subTest(document_id=document_id):
                stream, authz, storage, events = self.fixture()
                with self.assertRaises(ValueError):
                    export_document(self.context, document_id, authz, storage)
                self.assertEqual(events, [])
                self.assertEqual(stream.close_calls, 0)

    def test_valid_ids_scoping_result_and_order(self):
        for document_id in ["a", "A0_-", "a" * 64, "_", "-"]:
            with self.subTest(document_id=document_id):
                stream, authz, storage, events = self.fixture(b"payload")
                result = export_document(self.context, document_id, authz, storage)
                self.assertEqual(result, storage.reference)
                self.assertEqual(authz.calls, [(self.context, document_id)] * 2)
                self.assertEqual(storage.open_calls, [(self.context.tenant_id, document_id)])
                self.assertEqual(storage.publish_calls, [
                    (self.context.tenant_id, self.context.principal_id, document_id, b"payload")
                ])
                self.assertIsInstance(storage.publish_calls[0][3], bytes)
                self.assertEqual(events, ["authorize", "open", "read", "read",
                                          "authorize", "publish", "close"])
                self.assertEqual(stream.close_calls, 1)

    def test_initial_denial_never_opens_or_publishes(self):
        stream, authz, storage, events = self.fixture(decisions=(False,))
        with self.assertRaises(PermissionError):
            export_document(self.context, "doc", authz, storage)
        self.assertEqual(events, ["authorize"])
        self.assertEqual(stream.close_calls, 0)

    def test_initial_authorization_errors_propagate(self):
        for failure in [TimeoutError("private provider detail"), RuntimeError("private provider detail")]:
            with self.subTest(error_type=type(failure).__name__):
                stream, authz, storage, events = self.fixture(decisions=(failure,))
                with self.assertRaises(type(failure)) as caught:
                    export_document(self.context, "doc", authz, storage)
                self.assertIs(caught.exception, failure)
                self.assertEqual(events, ["authorize"])
                self.assertEqual(stream.close_calls, 0)

    def test_open_failure_propagates_without_publish(self):
        failure = OSError("private provider detail")
        stream, authz, storage, events = self.fixture(open_error=failure)
        with self.assertRaises(OSError) as caught:
            export_document(self.context, "doc", authz, storage)
        self.assertIs(caught.exception, failure)
        self.assertEqual(events, ["authorize", "open"])
        self.assertEqual(stream.close_calls, 0)

    def test_empty_and_limit_sized_documents(self):
        for size in [0, 1, 4095, 4096]:
            with self.subTest(size=size):
                content = b"x" * size
                stream, authz, storage, events = self.fixture(content)
                export_document(self.context, "doc", authz, storage)
                self.assertEqual(storage.publish_calls[0][3], content)
                self.assertEqual(stream.position, size)
                self.assertEqual(stream.requests, [4097] if size == 0 else [4097, 4097 - size])
                self.assertEqual(stream.close_calls, 1)

    def test_short_reads_continue_until_eof(self):
        content = bytes(range(256)) * 16
        stream, authz, storage, events = self.fixture(content, chunk_size=7)
        export_document(self.context, "doc", authz, storage)
        self.assertEqual(storage.publish_calls[0][3], content)
        self.assertGreater(len(stream.requests), 2)
        self.assertEqual(stream.requests[-1], 1)
        self.assertEqual(stream.position, 4096)
        self.assertEqual(stream.close_calls, 1)

    def test_oversize_reads_at_most_one_byte_beyond_limit(self):
        for size, chunk_size in [(4097, None), (100000, None), (4097, 3), (100000, 1)]:
            with self.subTest(size=size, chunk_size=chunk_size):
                stream, authz, storage, events = self.fixture(b"x" * size, chunk_size=chunk_size)
                with self.assertRaises(ValueError):
                    export_document(self.context, "doc", authz, storage)
                self.assertEqual(stream.position, 4097)
                self.assertEqual(storage.publish_calls, [])
                self.assertEqual(len(authz.calls), 1)
                self.assertEqual(stream.close_calls, 1)

    def test_revoked_permission_prevents_publication(self):
        stream, authz, storage, events = self.fixture(decisions=(True, False))
        with self.assertRaises(PermissionError):
            export_document(self.context, "doc", authz, storage)
        self.assertEqual(len(authz.calls), 2)
        self.assertEqual(storage.publish_calls, [])
        self.assertEqual(events[-2:], ["authorize", "close"])
        self.assertEqual(stream.close_calls, 1)

    def test_final_authorization_error_propagates_and_closes(self):
        failure = TimeoutError("private provider detail")
        stream, authz, storage, events = self.fixture(decisions=(True, failure))
        with self.assertRaises(TimeoutError) as caught:
            export_document(self.context, "doc", authz, storage)
        self.assertIs(caught.exception, failure)
        self.assertEqual(storage.publish_calls, [])
        self.assertEqual(stream.close_calls, 1)

    def test_read_failure_closes_without_publication(self):
        failure = OSError("private provider detail")
        stream, authz, storage, events = self.fixture(read_error=failure, fail_after_reads=1, chunk_size=2)
        with self.assertRaises(OSError) as caught:
            export_document(self.context, "doc", authz, storage)
        self.assertIs(caught.exception, failure)
        self.assertEqual(stream.position, 2)
        self.assertEqual(storage.publish_calls, [])
        self.assertEqual(stream.close_calls, 1)

    def test_publish_failure_is_not_retried(self):
        failure = TimeoutError("publish may already be committed")
        stream, authz, storage, events = self.fixture(publish_error=failure)
        with self.assertRaises(TimeoutError) as caught:
            export_document(self.context, "doc", authz, storage)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(storage.publish_calls), 1)
        self.assertEqual(len(authz.calls), 2)
        self.assertEqual(stream.close_calls, 1)

    def test_cleanup_alone_failure_propagates_without_retry(self):
        failure = OSError("private cleanup detail")
        stream, authz, storage, events = self.fixture(close_error=failure)
        with self.assertRaises(OSError) as caught:
            export_document(self.context, "doc", authz, storage)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(storage.publish_calls), 1)
        self.assertEqual(stream.close_calls, 1)

    def test_cleanup_failure_preserves_original_errors_and_secondary_cause(self):
        for stage in ["read", "authorization", "publish"]:
            with self.subTest(stage=stage):
                primary = RuntimeError("private primary detail")
                cleanup = OSError("private cleanup detail")
                options = {"close_error": cleanup}
                if stage == "read":
                    options["read_error"] = primary
                elif stage == "authorization":
                    options["decisions"] = (True, primary)
                else:
                    options["publish_error"] = primary
                stream, authz, storage, events = self.fixture(**options)
                with self.assertRaises(RuntimeError) as caught:
                    export_document(self.context, "doc", authz, storage)
                self.assertIs(caught.exception, primary)
                self.assertIs(caught.exception.__cause__, cleanup)
                self.assertEqual(stream.close_calls, 1)

    def test_denial_and_overflow_also_survive_cleanup_failure(self):
        for content, decisions, error_type in [
            (b"content", (True, False), PermissionError),
            (b"x" * 4097, (True, True), ValueError),
        ]:
            with self.subTest(error_type=error_type.__name__):
                cleanup = OSError("private cleanup detail")
                stream, authz, storage, events = self.fixture(content, decisions=decisions, close_error=cleanup)
                with self.assertRaises(error_type) as caught:
                    export_document(self.context, "doc", authz, storage)
                self.assertIs(caught.exception.__cause__, cleanup)
                self.assertEqual(storage.publish_calls, [])
                self.assertEqual(stream.close_calls, 1)

    def test_base_exception_still_closes_stream(self):
        failure = KeyboardInterrupt()
        stream, authz, storage, events = self.fixture(read_error=failure)
        with self.assertRaises(KeyboardInterrupt) as caught:
            export_document(self.context, "doc", authz, storage)
        self.assertIs(caught.exception, failure)
        self.assertEqual(stream.close_calls, 1)

    def test_non_binary_read_fails_closed(self):
        stream, authz, storage, events = self.fixture()
        stream.read = lambda size: None
        with self.assertRaises(TypeError):
            export_document(self.context, "doc", authz, storage)
        self.assertEqual(storage.publish_calls, [])
        self.assertEqual(stream.close_calls, 1)

    def test_success_and_failures_do_not_print_sensitive_data(self):
        output = io.StringIO()
        failures = [None, OSError("PRIVATE_PROVIDER_ERROR")]
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            for failure in failures:
                stream, authz, storage, events = self.fixture(b"PRIVATE_DOCUMENT", publish_error=failure)
                try:
                    export_document(self.context, "doc", authz, storage)
                except OSError:
                    pass
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
