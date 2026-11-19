"""Local, dependency-free regression checks for payment ownership and recovery."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
import unittest

from payment import PaymentResult, Store, reconcile, submit


PENDING = PaymentResult("pending", None)


class FakeProvider:
    def __init__(self, receipts=None):
        self.receipts = {} if receipts is None else receipts
        self.charge_calls = []
        self.lookup_calls = []
        self.charge_error = None
        self.lookup_error = None
        self.commit_before_error = False
        self.lock = Lock()

    def charge(self, key, amount_cents):
        with self.lock:
            self.charge_calls.append((key, amount_cents))
            receipt = "receipt:" + key
            if self.charge_error is None or self.commit_before_error:
                self.receipts[key] = receipt
            error = self.charge_error
        if error is not None:
            raise error
        return receipt

    def lookup(self, key):
        with self.lock:
            self.lookup_calls.append(key)
            error = self.lookup_error
            receipt = self.receipts.get(key)
        if error is not None:
            raise error
        return receipt


class PaymentTests(unittest.TestCase):
    def test_invalid_inputs_fail_before_any_provider_call(self):
        bad_ids = [None, 12, True, b"op", "", "x" * 65, "caf\u00e9",
                   "with space", "op\n", "op/id", "op.id", "\uff11"]
        bad_amounts = [None, True, False, 1.0, "1", 0, -1, 100_000_001,
                       float("nan"), float("inf")]
        for function in (submit, reconcile):
            for field in ("operation_id", "tenant_id", "amount_cents"):
                for value in bad_amounts if field == "amount_cents" else bad_ids:
                    with self.subTest(function=function.__name__, field=field, value=value):
                        store, provider = Store(), FakeProvider()
                        kwargs = dict(operation_id="op", tenant_id="tenant", amount_cents=1)
                        kwargs[field] = value
                        with self.assertRaises(ValueError):
                            function(store, provider, **kwargs)
                        self.assertEqual(provider.charge_calls, [])
                        self.assertEqual(provider.lookup_calls, [])
                        self.assertEqual(store.results, {})

    def test_valid_boundaries_and_completed_duplicates(self):
        for operation_id, tenant_id, amount in (("A", "_", 1),
                                                ("x" * 62 + "_-", "t" * 64, 100_000_000)):
            with self.subTest(amount=amount):
                store, provider = Store(), FakeProvider()
                result = submit(store, provider, operation_id, tenant_id, amount)
                self.assertEqual(result, PaymentResult("completed", "receipt:" + operation_id))
                self.assertIs(store.results[operation_id], result)
                self.assertEqual(submit(store, provider, operation_id, tenant_id, amount), result)
                self.assertEqual(reconcile(store, provider, operation_id, tenant_id, amount), result)
                self.assertEqual(provider.charge_calls, [(operation_id, amount)])
                self.assertEqual(provider.lookup_calls, [])

    def test_mismatched_owner_or_amount_cannot_read_pending_or_completed_operation(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                store, provider = Store(), FakeProvider()
                if pending:
                    provider.charge_error = TimeoutError("after commit")
                    provider.commit_before_error = True
                submit(store, provider, "op", "tenant", 100)
                before = store.results["op"]
                for function in (submit, reconcile):
                    for tenant, amount in (("other", 100), ("tenant", 101)):
                        with self.assertRaises(ValueError) as caught:
                            function(store, provider, "op", tenant, amount)
                        self.assertNotIn("receipt:op", str(caught.exception))
                        self.assertIs(store.results["op"], before)
                self.assertEqual(provider.charge_calls, [("op", 100)])
                self.assertEqual(provider.lookup_calls, [])

    def test_timeout_and_connection_error_recover_using_original_identity(self):
        for error in (TimeoutError("committed"), ConnectionError("committed")):
            with self.subTest(error=type(error).__name__):
                store, provider = Store(), FakeProvider()
                provider.charge_error = error
                provider.commit_before_error = True
                self.assertEqual(submit(store, provider, "op", "tenant", 100), PENDING)
                self.assertEqual(store.results["op"], PENDING)
                self.assertEqual(submit(store, provider, "op", "tenant", 100), PENDING)
                # A new worker/provider wrapper uses the same accepted Store record.
                restarted_provider = FakeProvider(provider.receipts)
                result = reconcile(store, restarted_provider, "op", "tenant", 100)
                self.assertEqual(result, PaymentResult("completed", "receipt:op"))
                self.assertIs(store.results["op"], result)
                self.assertEqual(provider.charge_calls, [("op", 100)])
                self.assertEqual(restarted_provider.charge_calls, [])
                self.assertEqual(restarted_provider.lookup_calls, ["op"])

    def test_expired_or_inconclusive_lookup_never_causes_resubmission(self):
        store, provider = Store(), FakeProvider()
        provider.charge_error = TimeoutError("committed")
        provider.commit_before_error = True
        self.assertEqual(submit(store, provider, "op", "tenant", 100), PENDING)
        provider.receipts.clear()  # Model an expired deduplication/status window.
        provider.charge_error = None
        for _ in range(5):
            self.assertEqual(reconcile(store, provider, "op", "tenant", 100), PENDING)
            self.assertEqual(submit(store, provider, "op", "tenant", 100), PENDING)
        self.assertEqual(provider.charge_calls, [("op", 100)])
        self.assertEqual(provider.lookup_calls, ["op"] * 5)
        self.assertEqual(store.results["op"], PENDING)

    def test_transient_lookup_errors_leave_operation_pending(self):
        for error in (TimeoutError("lookup"), ConnectionError("lookup")):
            with self.subTest(error=type(error).__name__):
                store, provider = Store(), FakeProvider()
                provider.charge_error = TimeoutError("committed")
                provider.commit_before_error = True
                submit(store, provider, "op", "tenant", 100)
                provider.lookup_error = error
                self.assertEqual(reconcile(store, provider, "op", "tenant", 100), PENDING)
                self.assertEqual(submit(store, provider, "op", "tenant", 100), PENDING)
                provider.lookup_error = None
                self.assertEqual(reconcile(store, provider, "op", "tenant", 100),
                                 PaymentResult("completed", "receipt:op"))
                self.assertEqual(provider.charge_calls, [("op", 100)])

    def test_unexpected_charge_exception_propagates_without_losing_record(self):
        for committed in (False, True):
            with self.subTest(committed=committed):
                store, provider = Store(), FakeProvider()
                error = RuntimeError("unexpected provider failure")
                provider.charge_error = error
                provider.commit_before_error = committed
                with self.assertRaises(RuntimeError) as caught:
                    submit(store, provider, "op", "tenant", 100)
                self.assertIs(caught.exception, error)
                self.assertEqual(store.results["op"], PENDING)
                provider.charge_error = None
                self.assertEqual(submit(store, provider, "op", "tenant", 100), PENDING)
                expected = PaymentResult("completed", "receipt:op") if committed else PENDING
                self.assertEqual(reconcile(store, provider, "op", "tenant", 100), expected)
                self.assertEqual(provider.charge_calls, [("op", 100)])

    def test_unexpected_lookup_exception_propagates_and_can_be_reconciled_later(self):
        store, provider = Store(), FakeProvider()
        provider.charge_error = TimeoutError("committed")
        provider.commit_before_error = True
        submit(store, provider, "op", "tenant", 100)
        error = RuntimeError("lookup bug")
        provider.lookup_error = error
        with self.assertRaises(RuntimeError) as caught:
            reconcile(store, provider, "op", "tenant", 100)
        self.assertIs(caught.exception, error)
        self.assertEqual(store.results["op"], PENDING)
        self.assertEqual(submit(store, provider, "op", "tenant", 100), PENDING)
        provider.lookup_error = None
        self.assertEqual(reconcile(store, provider, "op", "tenant", 100),
                         PaymentResult("completed", "receipt:op"))
        self.assertEqual(provider.charge_calls, [("op", 100)])

    def test_concurrent_duplicates_and_unrelated_payment_do_not_wait_for_slow_charge(self):
        started, release = Event(), Event()

        class SlowProvider(FakeProvider):
            def charge(self, key, amount):
                receipt = super().charge(key, amount)
                if key == "slow":
                    started.set()
                    if not release.wait(5):
                        raise AssertionError("test did not release charge")
                return receipt

        store, provider = Store(), SlowProvider()
        with ThreadPoolExecutor(max_workers=16) as pool:
            first = pool.submit(submit, store, provider, "slow", "tenant", 100)
            try:
                self.assertTrue(started.wait(2))
                duplicates = [pool.submit(submit, store, provider, "slow", "tenant", 100)
                              for _ in range(12)]
                for future in duplicates:
                    self.assertEqual(future.result(timeout=2), PENDING)
                unrelated = pool.submit(submit, store, provider, "other", "tenant", 200)
                self.assertEqual(unrelated.result(timeout=2),
                                 PaymentResult("completed", "receipt:other"))
                mismatch = pool.submit(submit, store, provider, "slow", "intruder", 100)
                with self.assertRaises(ValueError):
                    mismatch.result(timeout=2)
                self.assertEqual(provider.charge_calls, [("slow", 100), ("other", 200)])
            finally:
                release.set()
            self.assertEqual(first.result(timeout=2), PaymentResult("completed", "receipt:slow"))

    def test_slow_lookup_does_not_block_unrelated_submission(self):
        started, release = Event(), Event()

        class SlowLookup(FakeProvider):
            def lookup(self, key):
                result = super().lookup(key)
                started.set()
                if not release.wait(5):
                    raise AssertionError("test did not release lookup")
                return result

        store, provider = Store(), SlowLookup()
        provider.charge_error = TimeoutError("unknown")
        submit(store, provider, "op", "tenant", 100)
        provider.charge_error = None
        with ThreadPoolExecutor(max_workers=2) as pool:
            recovery = pool.submit(reconcile, store, provider, "op", "tenant", 100)
            try:
                self.assertTrue(started.wait(2))
                unrelated = pool.submit(submit, store, provider, "other", "tenant", 200)
                self.assertEqual(unrelated.result(timeout=2),
                                 PaymentResult("completed", "receipt:other"))
            finally:
                release.set()
            self.assertEqual(recovery.result(timeout=2), PENDING)

    def test_reconciliation_can_complete_while_original_charge_finishes_with_error(self):
        started, release = Event(), Event()

        class CommittedSlowCharge(FakeProvider):
            def charge(self, key, amount):
                super().charge(key, amount)
                started.set()
                if not release.wait(5):
                    raise AssertionError("test did not release charge")
                raise TimeoutError("response lost after commit")

        store, provider = Store(), CommittedSlowCharge()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(submit, store, provider, "op", "tenant", 100)
            try:
                self.assertTrue(started.wait(2))
                expected = PaymentResult("completed", "receipt:op")
                self.assertEqual(reconcile(store, provider, "op", "tenant", 100), expected)
                self.assertIsNotNone(store.results["op"].receipt)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=2), expected)
        self.assertEqual(provider.charge_calls, [("op", 100)])

    def test_late_inconclusive_lookup_does_not_downgrade_completed_result(self):
        for outcome in (None, TimeoutError("late"), ConnectionError("late")):
            with self.subTest(outcome=type(outcome).__name__):
                started, release = Event(), Event()

                class RacingLookup(FakeProvider):
                    def lookup(self, key):
                        with self.lock:
                            self.lookup_calls.append(key)
                            first = len(self.lookup_calls) == 1
                        if first:
                            started.set()
                            if not release.wait(5):
                                raise AssertionError("test did not release lookup")
                            if outcome is not None:
                                raise outcome
                            return None
                        return "receipt:op"

                store, provider = Store(), RacingLookup()
                provider.charge_error = TimeoutError("unknown")
                submit(store, provider, "op", "tenant", 100)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(reconcile, store, provider, "op", "tenant", 100)
                    try:
                        self.assertTrue(started.wait(2))
                        expected = PaymentResult("completed", "receipt:op")
                        self.assertEqual(reconcile(store, provider, "op", "tenant", 100), expected)
                    finally:
                        release.set()
                    self.assertEqual(first.result(timeout=2), expected)
                    self.assertEqual(store.results["op"], expected)
                self.assertEqual(provider.charge_calls, [("op", 100)])

    def test_unsubmitted_operation_cannot_be_reconciled_into_a_charge(self):
        store, provider = Store(), FakeProvider()
        with self.assertRaises(ValueError):
            reconcile(store, provider, "missing", "tenant", 100)
        self.assertEqual(store.results, {})
        self.assertEqual(provider.charge_calls, [])
        self.assertEqual(provider.lookup_calls, [])

    def test_empty_string_receipt_is_authoritative(self):
        class EmptyReceipt(FakeProvider):
            def charge(self, key, amount):
                super().charge(key, amount)
                return ""

        store, provider = Store(), EmptyReceipt()
        result = submit(store, provider, "op", "tenant", 1)
        self.assertEqual(result, PaymentResult("completed", ""))
        self.assertIs(store.results["op"], result)

    def test_malformed_provider_receipt_leaves_safe_pending_record(self):
        class BadReceipt(FakeProvider):
            def charge(self, key, amount):
                super().charge(key, amount)
                return None

        store, provider = Store(), BadReceipt()
        with self.assertRaises(TypeError):
            submit(store, provider, "op", "tenant", 1)
        self.assertEqual(store.results["op"], PENDING)
        self.assertEqual(submit(store, provider, "op", "tenant", 1), PENDING)
        self.assertEqual(reconcile(store, provider, "op", "tenant", 1),
                         PaymentResult("completed", "receipt:op"))
        self.assertEqual(provider.charge_calls, [("op", 1)])


if __name__ == "__main__":
    unittest.main()
