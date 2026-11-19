"""Local contract regressions; all providers are deterministic, in-memory fakes."""
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from payment import PaymentResult, Store, reconcile, submit


PENDING = PaymentResult("pending", None)


class FakeProvider:
    def __init__(self):
        self.lock = threading.Lock()
        self.charges = []
        self.lookups = []
        self.receipts = {}
        self.charge_error = None
        self.lookup_error = None
        self.commit = True

    def charge(self, key, amount_cents):
        with self.lock:
            self.charges.append((key, amount_cents))
            receipt = "private-receipt-" + key
            if self.commit:
                self.receipts[key] = receipt
        if self.charge_error is not None:
            raise self.charge_error
        return receipt

    def lookup(self, key):
        with self.lock:
            self.lookups.append(key)
            receipt = self.receipts.get(key)
        if self.lookup_error is not None:
            raise self.lookup_error
        return receipt


class BlockingProvider(FakeProvider):
    def __init__(self, blocked_method="charge"):
        super().__init__()
        self.blocked_method = blocked_method
        self.entered = threading.Event()
        self.release = threading.Event()

    def wait_for_release(self):
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("test provider release timed out")

    def charge(self, key, amount_cents):
        if self.blocked_method == "charge" and amount_cents == 123:
            self.wait_for_release()
        return super().charge(key, amount_cents)

    def lookup(self, key):
        if self.blocked_method == "lookup":
            self.wait_for_release()
        return super().lookup(key)


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.provider = FakeProvider()

    def test_invalid_input_rejected_before_any_provider_call(self):
        invalid_ids = [None, True, 1, [], b"abc", "", "a" * 65,
                       "has space", "a/b", "x\n", "caf\u00e9", "\u212a"]
        invalid_amounts = [None, True, False, [], "1", 1.0, float("nan"),
                           float("inf"), -1, 0, 100_000_001]
        for operation in (submit, reconcile):
            for value in invalid_ids:
                for field in (0, 1):
                    args = ["operation", "tenant", 123]
                    args[field] = value
                    with self.subTest(operation=operation.__name__, args=args):
                        provider = FakeProvider()
                        with self.assertRaises(ValueError):
                            operation(Store(), provider, *args)
                        self.assertEqual(provider.charges, [])
                        self.assertEqual(provider.lookups, [])
            for amount in invalid_amounts:
                with self.subTest(operation=operation.__name__, amount=amount):
                    provider = FakeProvider()
                    with self.assertRaises(ValueError):
                        operation(Store(), provider, "operation", "tenant", amount)
                    self.assertEqual(provider.charges, [])
                    self.assertEqual(provider.lookups, [])

    def test_valid_identifier_and_amount_boundaries(self):
        for operation_id, tenant_id, amount in [
            ("-", "_", 1), ("a" * 64, "Z09_-" + "x" * 59, 100_000_000),
        ]:
            with self.subTest(amount=amount):
                store = Store()
                provider = FakeProvider()
                result = submit(store, provider, operation_id, tenant_id, amount)
                self.assertEqual(result.status, "completed")
                self.assertEqual(store.results[operation_id], result)
                self.assertEqual(len(provider.charges), 1)

    def test_success_is_stored_and_duplicates_return_the_stored_result(self):
        result = submit(self.store, self.provider, "op", "tenant", 123)
        self.assertEqual(result.status, "completed")
        self.assertIs(self.store.results["op"], result)
        self.assertEqual(submit(self.store, self.provider, "op", "tenant", 123), result)
        self.assertEqual(reconcile(self.store, self.provider, "op", "tenant", 123), result)
        self.assertEqual(len(self.provider.charges), 1)
        self.assertEqual(self.provider.lookups, [])

    def test_ambiguous_charge_is_recorded_and_resolved_using_the_same_identity(self):
        for error in (TimeoutError("timeout"), ConnectionError("connection")):
            with self.subTest(error=type(error).__name__):
                store = Store()
                provider = FakeProvider()
                provider.charge_error = error
                self.assertEqual(submit(store, provider, "op", "tenant", 123), PENDING)
                self.assertEqual(store.results.get("op"), PENDING)
                self.assertEqual(submit(store, provider, "op", "tenant", 123), PENDING)
                result = reconcile(store, provider, "op", "tenant", 123)
                self.assertEqual(result.status, "completed")
                self.assertEqual(store.results["op"], result)
                self.assertEqual(len(provider.charges), 1)
                self.assertEqual(provider.lookups, [provider.charges[0][0]])

    def test_inconclusive_lookup_never_recharges_even_after_provider_forgets_key(self):
        self.provider.charge_error = TimeoutError()
        submit(self.store, self.provider, "op", "tenant", 123)
        self.provider.receipts.clear()  # Simulate expiry of provider retention.
        self.provider.charge_error = None
        for _ in range(3):
            self.assertEqual(reconcile(self.store, self.provider, "op", "tenant", 123), PENDING)
            self.assertEqual(submit(self.store, self.provider, "op", "tenant", 123), PENDING)
        self.assertEqual(len(self.provider.charges), 1)
        self.assertEqual(self.provider.lookups, [self.provider.charges[0][0]] * 3)
        self.assertEqual(self.store.results["op"], PENDING)

    def test_lookup_transient_failures_preserve_pending(self):
        self.provider.charge_error = TimeoutError()
        submit(self.store, self.provider, "op", "tenant", 123)
        for error in (TimeoutError(), ConnectionError()):
            self.provider.lookup_error = error
            self.assertEqual(reconcile(self.store, self.provider, "op", "tenant", 123), PENDING)
            self.assertEqual(self.store.results["op"], PENDING)
        self.provider.lookup_error = None
        self.assertEqual(reconcile(self.store, self.provider, "op", "tenant", 123).status,
                         "completed")
        self.assertEqual(len(self.provider.charges), 1)

    def test_conflicting_ownership_or_amount_rejected_on_completed_and_pending(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                store = Store()
                provider = FakeProvider()
                if pending:
                    provider.charge_error = TimeoutError()
                submit(store, provider, "op", "owner", 123)
                for operation in (submit, reconcile):
                    for tenant, amount in [("intruder", 123), ("owner", 124)]:
                        with self.assertRaises(ValueError) as caught:
                            operation(store, provider, "op", tenant, amount)
                        self.assertNotIn("private-receipt", str(caught.exception))
                self.assertEqual(len(provider.charges), 1)
                self.assertEqual(provider.lookups, [])

    def test_unexpected_charge_exception_propagates_and_can_be_reconciled(self):
        error = RuntimeError("unexpected provider failure")
        self.provider.charge_error = error
        with self.assertRaises(RuntimeError) as caught:
            submit(self.store, self.provider, "op", "tenant", 123)
        self.assertIs(caught.exception, error)
        self.assertEqual(self.store.results.get("op"), PENDING)
        self.assertEqual(submit(self.store, self.provider, "op", "tenant", 123), PENDING)
        self.assertEqual(reconcile(self.store, self.provider, "op", "tenant", 123).status,
                         "completed")
        self.assertEqual(len(self.provider.charges), 1)

    def test_unexpected_lookup_exception_propagates_without_losing_the_operation(self):
        self.provider.charge_error = TimeoutError()
        submit(self.store, self.provider, "op", "tenant", 123)
        error = RuntimeError("lookup failed")
        self.provider.lookup_error = error
        with self.assertRaises(RuntimeError) as caught:
            reconcile(self.store, self.provider, "op", "tenant", 123)
        self.assertIs(caught.exception, error)
        self.assertEqual(self.store.results["op"], PENDING)
        self.provider.lookup_error = None
        self.assertEqual(reconcile(self.store, self.provider, "op", "tenant", 123).status,
                         "completed")
        self.assertEqual(len(self.provider.charges), 1)

    def test_worker_cancellation_propagates_but_preserves_the_record(self):
        self.provider.charge_error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            submit(self.store, self.provider, "op", "tenant", 123)
        self.assertEqual(self.store.results.get("op"), PENDING)
        self.assertEqual(submit(self.store, self.provider, "op", "tenant", 123), PENDING)
        self.assertEqual(reconcile(self.store, self.provider, "op", "tenant", 123).status,
                         "completed")
        self.assertEqual(len(self.provider.charges), 1)

    def test_unknown_reconciliation_does_not_create_a_charge(self):
        with self.assertRaises(ValueError):
            reconcile(self.store, self.provider, "unknown", "tenant", 123)
        self.assertEqual(self.provider.charges, [])
        self.assertEqual(self.provider.lookups, [])
        self.assertEqual(self.store.results, {})

    def test_worker_restart_reuses_shared_store_and_original_key(self):
        self.provider.charge_error = TimeoutError()
        submit(self.store, self.provider, "op", "tenant", 123)
        replacement_worker_provider = FakeProvider()
        replacement_worker_provider.receipts = self.provider.receipts
        self.assertEqual(submit(self.store, replacement_worker_provider,
                                "op", "tenant", 123), PENDING)
        result = reconcile(self.store, replacement_worker_provider, "op", "tenant", 123)
        self.assertEqual(result.status, "completed")
        self.assertEqual(replacement_worker_provider.charges, [])
        self.assertEqual(replacement_worker_provider.lookups, [self.provider.charges[0][0]])

    def test_concurrent_duplicates_return_pending_and_unrelated_submit_can_finish(self):
        provider = BlockingProvider()
        with ThreadPoolExecutor(max_workers=10) as workers:
            first = workers.submit(submit, self.store, provider, "slow", "tenant", 123)
            try:
                self.assertTrue(provider.entered.wait(2))
                duplicates = [workers.submit(submit, self.store, provider,
                                             "slow", "tenant", 123) for _ in range(8)]
                for future in duplicates:
                    self.assertEqual(future.result(timeout=2), PENDING)
                unrelated = workers.submit(submit, self.store, provider,
                                           "fast", "tenant", 124)
                self.assertEqual(unrelated.result(timeout=2).status, "completed")
                for operation in (submit, reconcile):
                    conflict = workers.submit(operation, self.store, provider,
                                              "slow", "intruder", 123)
                    with self.assertRaises(ValueError):
                        conflict.result(timeout=2)
            finally:
                provider.release.set()
            self.assertEqual(first.result(timeout=2).status, "completed")
        self.assertEqual(sorted(amount for _, amount in provider.charges), [123, 124])

    def test_concurrent_first_submissions_make_only_one_charge(self):
        barrier = threading.Barrier(12)

        def call():
            barrier.wait(timeout=3)
            return submit(self.store, self.provider, "op", "tenant", 123)

        with ThreadPoolExecutor(max_workers=12) as workers:
            futures = [workers.submit(call) for _ in range(12)]
            results = [future.result(timeout=5) for future in futures]
        self.assertEqual(len(self.provider.charges), 1)
        self.assertTrue(all(result.status in ("pending", "completed") for result in results))
        self.assertEqual(self.store.results["op"].status, "completed")

    def test_slow_lookup_does_not_block_unrelated_operation(self):
        provider = BlockingProvider("lookup")
        provider.charge_error = TimeoutError()
        submit(self.store, provider, "slow", "tenant", 123)
        provider.charge_error = None
        with ThreadPoolExecutor(max_workers=2) as workers:
            slow = workers.submit(reconcile, self.store, provider, "slow", "tenant", 123)
            try:
                self.assertTrue(provider.entered.wait(2))
                fast = workers.submit(submit, self.store, provider, "fast", "tenant", 124)
                self.assertEqual(fast.result(timeout=2).status, "completed")
            finally:
                provider.release.set()
            self.assertEqual(slow.result(timeout=2).status, "completed")
        self.assertEqual(len(provider.charges), 2)

    def test_late_charge_timeout_does_not_downgrade_a_reconciled_receipt(self):
        provider = BlockingProvider()

        def committed_then_timeout(key, amount):
            with provider.lock:
                provider.charges.append((key, amount))
                provider.receipts[key] = "receipt-before-timeout"
            provider.wait_for_release()
            raise TimeoutError()

        provider.charge = committed_then_timeout
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(submit, self.store, provider, "op", "tenant", 123)
            try:
                self.assertTrue(provider.entered.wait(2))
                lookup = workers.submit(reconcile, self.store, provider, "op", "tenant", 123)
                result = lookup.result(timeout=2)
                self.assertEqual(result, PaymentResult("completed", "receipt-before-timeout"))
                self.assertEqual(self.store.results["op"], result)
            finally:
                provider.release.set()
            self.assertEqual(first.result(timeout=2), result)
        self.assertEqual(len(provider.charges), 1)

    def test_late_inconclusive_lookup_does_not_downgrade_completion(self):
        self.provider.charge_error = TimeoutError()
        submit(self.store, self.provider, "op", "tenant", 123)
        entered = threading.Event()
        release = threading.Event()
        original_lookup = self.provider.lookup
        call_lock = threading.Lock()
        calls = 0

        def lookup(key):
            nonlocal calls
            with call_lock:
                calls += 1
                first = calls == 1
            if first:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test release timed out")
                return None
            return original_lookup(key)

        self.provider.lookup = lookup
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(reconcile, self.store, self.provider, "op", "tenant", 123)
            try:
                self.assertTrue(entered.wait(2))
                second = workers.submit(reconcile, self.store, self.provider,
                                        "op", "tenant", 123)
                result = second.result(timeout=2)
                self.assertEqual(result.status, "completed")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=2), result)
        self.assertEqual(self.store.results["op"], result)
        self.assertEqual(len(self.provider.charges), 1)

    def test_malformed_charge_receipt_is_not_stored_as_completed(self):
        for receipt in (None, 123, [], False):
            with self.subTest(receipt=receipt):
                provider = FakeProvider()
                provider.charge = lambda key, amount: receipt
                store = Store()
                with self.assertRaises(TypeError):
                    submit(store, provider, "op", "tenant", 123)
                self.assertEqual(store.results.get("op"), PENDING)

    def test_malformed_lookup_receipt_leaves_operation_reconcilable(self):
        self.provider.charge_error = TimeoutError()
        submit(self.store, self.provider, "op", "tenant", 123)
        original_lookup = self.provider.lookup
        self.provider.lookup = lambda key: 123
        with self.assertRaises(TypeError):
            reconcile(self.store, self.provider, "op", "tenant", 123)
        self.assertEqual(self.store.results["op"], PENDING)
        self.provider.lookup = original_lookup
        self.assertEqual(reconcile(self.store, self.provider, "op", "tenant", 123).status,
                         "completed")

    def test_empty_string_is_a_receipt_under_the_provider_contract(self):
        self.provider.charge = lambda key, amount: ""
        self.assertEqual(submit(self.store, self.provider, "op", "tenant", 123),
                         PaymentResult("completed", ""))


if __name__ == "__main__":
    unittest.main()
