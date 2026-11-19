"""Contract regressions using only local, controllable providers."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from payment import PaymentResult, Store, reconcile, submit


PENDING = PaymentResult("pending", None)


class FakeProvider:
    def __init__(self, charge_error=None, commit=True):
        self.charge_error = charge_error
        self.lookup_error = None
        self.commit = commit
        self.receipts = {}
        self.charge_calls = []
        self.lookup_calls = []
        self.effects = 0
        self.lock = Lock()

    def charge(self, key, amount_cents):
        with self.lock:
            self.charge_calls.append((key, amount_cents))
            if self.commit and key not in self.receipts:
                self.effects += 1
                self.receipts[key] = "receipt-" + str(self.effects)
            receipt = self.receipts.get(key)
        if self.charge_error is not None:
            raise self.charge_error
        return receipt

    def lookup(self, key):
        with self.lock:
            self.lookup_calls.append(key)
            receipt = self.receipts.get(key)
        if self.lookup_error is not None:
            raise self.lookup_error
        return receipt


class BlockingChargeProvider(FakeProvider):
    def __init__(self, commit_first=False, charge_error=None):
        super().__init__()
        self.started = Event()
        self.release = Event()
        self.commit_first = commit_first
        self.after_wait_error = charge_error

    def charge(self, key, amount_cents):
        if amount_cents != 10:
            return super().charge(key, amount_cents)
        receipt = super().charge(key, amount_cents) if self.commit_first else None
        self.started.set()
        if not self.release.wait(5):
            raise RuntimeError("test did not release charge")
        if self.after_wait_error is not None:
            raise self.after_wait_error
        return receipt if self.commit_first else super().charge(key, amount_cents)


class PaymentTests(unittest.TestCase):
    def test_success_is_stored_and_duplicate_is_read_only(self):
        store, provider = Store(), FakeProvider()
        result = submit(store, provider, "op", "tenant", 10)
        self.assertEqual(result, PaymentResult("completed", "receipt-1"))
        self.assertEqual(store.results["op"], result)
        self.assertEqual(submit(store, provider, "op", "tenant", 10), result)
        self.assertEqual(reconcile(store, provider, "op", "tenant", 10), result)
        self.assertEqual(len(provider.charge_calls), 1)
        self.assertEqual(provider.lookup_calls, [])

    def test_invalid_inputs_rejected_before_any_provider_call(self):
        invalid_ids = (None, True, 1, b"id", "", "x" * 65, "a b", "a/b",
                       "a\n", "é", "Ａ", "a\x00", "a.b")
        invalid_amounts = (None, True, False, 0, -1, 100_000_001, 1.0, "1", [],
                           float("nan"), float("inf"), 10 ** 100)
        for function in (submit, reconcile):
            cases = [(bad, "tenant", 1) for bad in invalid_ids]
            cases += [("op", bad, 1) for bad in invalid_ids]
            cases += [("op", "tenant", bad) for bad in invalid_amounts]
            for arguments in cases:
                with self.subTest(function=function.__name__, arguments=arguments):
                    store, provider = Store(), FakeProvider()
                    with self.assertRaises(ValueError):
                        function(store, provider, *arguments)
                    self.assertEqual(provider.charge_calls, [])
                    self.assertEqual(provider.lookup_calls, [])
                    self.assertEqual(store.results, {})

    def test_valid_boundaries_and_ascii_punctuation(self):
        for index, (operation, tenant, amount) in enumerate((
            ("a", "0", 1), ("A" * 64, "_" * 64, 100_000_000),
            ("aA0_-", "Tenant-2_", 7),
        )):
            with self.subTest(index=index):
                provider = FakeProvider()
                result = submit(Store(), provider, operation, tenant, amount)
                self.assertEqual(result.status, "completed")
                self.assertEqual(provider.charge_calls[0][1], amount)

    def test_conflicting_reuse_rejected_without_receipt(self):
        for pending in (False, True):
            store = Store()
            provider = FakeProvider(TimeoutError("lost response") if pending else None)
            submit(store, provider, "op", "tenant", 10)
            for function in (submit, reconcile):
                for tenant, amount in (("other", 10), ("tenant", 11), ("other", 11)):
                    with self.subTest(pending=pending, function=function.__name__, tenant=tenant):
                        with self.assertRaises(ValueError) as caught:
                            function(store, provider, "op", tenant, amount)
                        self.assertNotIn("receipt-1", str(caught.exception))
            self.assertEqual(len(provider.charge_calls), 1)
            self.assertEqual(provider.lookup_calls, [])

    def test_timeout_or_connection_error_after_commit_recovers_same_identity(self):
        for error in (TimeoutError("timeout"), ConnectionError("reset")):
            with self.subTest(error=type(error).__name__):
                store, provider = Store(), FakeProvider(error)
                self.assertEqual(submit(store, provider, "op", "tenant", 10), PENDING)
                self.assertEqual(store.results["op"], PENDING)
                self.assertEqual(submit(store, provider, "op", "tenant", 10), PENDING)
                result = reconcile(store, provider, "op", "tenant", 10)
                self.assertEqual(result, PaymentResult("completed", "receipt-1"))
                self.assertEqual(store.results["op"], result)
                self.assertEqual(len(provider.charge_calls), 1)
                self.assertEqual(provider.lookup_calls, [provider.charge_calls[0][0]])
                self.assertEqual(provider.effects, 1)

    def test_inconclusive_lookup_and_expired_provider_retention_never_recharge(self):
        store, provider = Store(), FakeProvider(TimeoutError("timeout"))
        self.assertEqual(submit(store, provider, "op", "tenant", 10), PENDING)
        provider.receipts.clear()  # Simulate provider retention expiring.
        for _ in range(3):
            self.assertEqual(reconcile(store, provider, "op", "tenant", 10), PENDING)
            self.assertEqual(submit(store, provider, "op", "tenant", 10), PENDING)
        self.assertEqual(len(provider.charge_calls), 1)
        self.assertEqual(provider.effects, 1)
        self.assertEqual(len(set(provider.lookup_calls)), 1)

    def test_no_commit_is_still_uncertain(self):
        store, provider = Store(), FakeProvider(ConnectionError("unknown"), commit=False)
        self.assertEqual(submit(store, provider, "op", "tenant", 10), PENDING)
        self.assertEqual(reconcile(store, provider, "op", "tenant", 10), PENDING)
        self.assertEqual(submit(store, provider, "op", "tenant", 10), PENDING)
        self.assertEqual(len(provider.charge_calls), 1)
        self.assertEqual(provider.effects, 0)

    def test_transient_lookup_failure_then_recovery(self):
        for error in (TimeoutError("timeout"), ConnectionError("reset")):
            with self.subTest(error=type(error).__name__):
                store, provider = Store(), FakeProvider(TimeoutError("lost response"))
                submit(store, provider, "op", "tenant", 10)
                provider.lookup_error = error
                self.assertEqual(reconcile(store, provider, "op", "tenant", 10), PENDING)
                self.assertEqual(store.results["op"], PENDING)
                provider.lookup_error = None
                self.assertEqual(reconcile(store, provider, "op", "tenant", 10).status, "completed")
                self.assertEqual(len(provider.charge_calls), 1)

    def test_unexpected_charge_failure_propagates_and_remains_recoverable(self):
        for error in (RuntimeError("provider bug"), KeyboardInterrupt("worker stopped")):
            with self.subTest(error=type(error).__name__):
                store, provider = Store(), FakeProvider(error)
                with self.assertRaises(type(error)) as caught:
                    submit(store, provider, "op", "tenant", 10)
                self.assertIs(caught.exception, error)
                self.assertEqual(store.results["op"], PENDING)
                self.assertEqual(submit(store, provider, "op", "tenant", 10), PENDING)
                self.assertEqual(reconcile(store, provider, "op", "tenant", 10).status, "completed")
                self.assertEqual(len(provider.charge_calls), 1)

    def test_unexpected_lookup_failure_propagates_and_remains_recoverable(self):
        store, provider = Store(), FakeProvider(TimeoutError("timeout"))
        submit(store, provider, "op", "tenant", 10)
        failure = RuntimeError("lookup bug")
        provider.lookup_error = failure
        with self.assertRaises(RuntimeError) as caught:
            reconcile(store, provider, "op", "tenant", 10)
        self.assertIs(caught.exception, failure)
        self.assertEqual(store.results["op"], PENDING)
        provider.lookup_error = None
        self.assertEqual(reconcile(store, provider, "op", "tenant", 10).status, "completed")
        self.assertEqual(len(provider.charge_calls), 1)

    def test_unknown_operation_reconciliation_rejects_without_provider_calls(self):
        store, provider = Store(), FakeProvider()
        with self.assertRaises(ValueError):
            reconcile(store, provider, "unknown", "tenant", 10)
        self.assertEqual(provider.charge_calls, [])
        self.assertEqual(provider.lookup_calls, [])
        self.assertEqual(store.results, {})

    def test_invalid_charge_receipt_cannot_become_completed(self):
        for invalid in (None, 42, True, [], {}):
            with self.subTest(invalid=invalid):
                store, provider = Store(), FakeProvider()
                real_charge = provider.charge

                def invalid_charge(key, amount):
                    real_charge(key, amount)
                    return invalid

                provider.charge = invalid_charge
                with self.assertRaises(TypeError):
                    submit(store, provider, "op", "tenant", 10)
                self.assertEqual(store.results["op"], PENDING)
                self.assertEqual(submit(store, provider, "op", "tenant", 10), PENDING)
                self.assertEqual(reconcile(store, provider, "op", "tenant", 10).status, "completed")
                self.assertEqual(len(provider.charge_calls), 1)

    def test_invalid_lookup_receipt_does_not_destroy_pending_state(self):
        store, provider = Store(), FakeProvider(TimeoutError("timeout"))
        submit(store, provider, "op", "tenant", 10)
        real_lookup = provider.lookup
        provider.lookup = lambda key: 123
        with self.assertRaises(TypeError):
            reconcile(store, provider, "op", "tenant", 10)
        self.assertEqual(store.results["op"], PENDING)
        provider.lookup = real_lookup
        self.assertEqual(reconcile(store, provider, "op", "tenant", 10).status, "completed")
        self.assertEqual(len(provider.charge_calls), 1)

    def test_worker_restart_reuses_accepted_store_and_provider_key(self):
        store, first_worker = Store(), FakeProvider(TimeoutError("worker lost reply"))
        submit(store, first_worker, "op", "tenant", 10)
        next_worker = FakeProvider()
        next_worker.receipts = dict(first_worker.receipts)
        self.assertEqual(submit(store, next_worker, "op", "tenant", 10), PENDING)
        result = reconcile(store, next_worker, "op", "tenant", 10)
        self.assertEqual(result, PaymentResult("completed", "receipt-1"))
        self.assertEqual(next_worker.charge_calls, [])
        self.assertEqual(next_worker.lookup_calls, [first_worker.charge_calls[0][0]])

    def test_inflight_duplicate_and_unrelated_operation_do_not_wait_for_charge(self):
        store, provider = Store(), BlockingChargeProvider()
        with ThreadPoolExecutor(max_workers=4) as workers:
            original = workers.submit(submit, store, provider, "slow", "tenant", 10)
            try:
                self.assertTrue(provider.started.wait(2))
                self.assertEqual(store.results["slow"], PENDING)
                duplicate = workers.submit(submit, store, provider, "slow", "tenant", 10)
                other = workers.submit(submit, store, provider, "fast", "tenant", 20)
                self.assertEqual(duplicate.result(timeout=2), PENDING)
                self.assertEqual(other.result(timeout=2).status, "completed")
                self.assertEqual(reconcile(store, provider, "slow", "tenant", 10), PENDING)
                conflict = workers.submit(submit, store, provider, "slow", "other", 10)
                with self.assertRaises(ValueError):
                    conflict.result(timeout=2)
            finally:
                provider.release.set()
            self.assertEqual(original.result(timeout=2).status, "completed")
        self.assertEqual(len(provider.charge_calls), 2)
        self.assertEqual(provider.effects, 2)

    def test_many_concurrent_duplicates_have_one_charge(self):
        store, provider = Store(), BlockingChargeProvider()
        with ThreadPoolExecutor(max_workers=12) as workers:
            original = workers.submit(submit, store, provider, "op", "tenant", 10)
            try:
                self.assertTrue(provider.started.wait(2))
                duplicates = [workers.submit(submit, store, provider, "op", "tenant", 10)
                              for _ in range(32)]
                self.assertEqual([future.result(timeout=2) for future in duplicates], [PENDING] * 32)
            finally:
                provider.release.set()
            self.assertEqual(original.result(timeout=2).status, "completed")
        self.assertEqual(len(provider.charge_calls), 1)
        self.assertEqual(provider.effects, 1)

    def test_reconcile_completion_survives_original_charge_timeout(self):
        store = Store()
        provider = BlockingChargeProvider(commit_first=True, charge_error=TimeoutError("late"))
        with ThreadPoolExecutor(max_workers=1) as workers:
            original = workers.submit(submit, store, provider, "op", "tenant", 10)
            try:
                self.assertTrue(provider.started.wait(2))
                completed = reconcile(store, provider, "op", "tenant", 10)
                self.assertEqual(completed, PaymentResult("completed", "receipt-1"))
            finally:
                provider.release.set()
            self.assertEqual(original.result(timeout=2), completed)
        self.assertEqual(store.results["op"], completed)
        self.assertEqual(provider.effects, 1)

    def test_stale_lookup_cannot_downgrade_completion_or_block_other_operations(self):
        for late_error in (None, TimeoutError("late"), ConnectionError("late")):
            with self.subTest(late_error=late_error):
                store, provider = Store(), FakeProvider(TimeoutError("timeout"))
                submit(store, provider, "op", "tenant", 10)
                started, release = Event(), Event()
                normal_lookup = provider.lookup
                first = True
                lock = Lock()

                def delayed_lookup(key):
                    nonlocal first
                    with lock:
                        delayed = first
                        first = False
                    if not delayed:
                        return normal_lookup(key)
                    started.set()
                    if not release.wait(5):
                        raise RuntimeError("test did not release lookup")
                    if late_error is not None:
                        raise late_error
                    return None

                provider.lookup = delayed_lookup
                provider.charge_error = None
                with ThreadPoolExecutor(max_workers=2) as workers:
                    slow = workers.submit(reconcile, store, provider, "op", "tenant", 10)
                    try:
                        self.assertTrue(started.wait(2))
                        other = workers.submit(submit, store, provider, "other", "tenant", 20)
                        self.assertEqual(other.result(timeout=2).status, "completed")
                        completed = reconcile(store, provider, "op", "tenant", 10)
                        self.assertEqual(completed, PaymentResult("completed", "receipt-1"))
                    finally:
                        release.set()
                    self.assertEqual(slow.result(timeout=2), completed)
                self.assertEqual(store.results["op"], completed)
                self.assertEqual(len(provider.charge_calls), 2)


if __name__ == "__main__":
    unittest.main()
