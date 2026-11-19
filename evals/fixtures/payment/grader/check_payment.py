"""Behavioral acceptance checks. Do not expose to the implementation agent."""
from __future__ import annotations

import importlib.util
import sys
import threading
import unittest
from pathlib import Path


TARGET = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("payment", TARGET / "payment.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load payment fixture")
payment = importlib.util.module_from_spec(spec)
sys.modules["payment"] = payment
spec.loader.exec_module(payment)


class Provider:
    def __init__(self, charge_error=None, lookup_error=None):
        self.calls = []
        self.receipts = {}
        self.charge_error = charge_error
        self.lookup_error = lookup_error

    def charge(self, key, amount_cents):
        self.calls.append((key, amount_cents))
        receipt = self.receipts.setdefault(key, "receipt-" + str(len(self.receipts) + 1))
        if self.charge_error:
            raise self.charge_error
        return receipt

    def lookup(self, key):
        if self.lookup_error:
            raise self.lookup_error
        return self.receipts.get(key)


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.store = payment.Store()

    def test_success_replay_uses_saved_receipt(self):
        provider = Provider()
        first = payment.submit(self.store, provider, "op_1", "tenant_A", 123)
        second = payment.submit(self.store, provider, "op_1", "tenant_A", 123)
        self.assertEqual(first.status, "completed")
        self.assertEqual(first, second)
        self.assertEqual(len(provider.calls), 1)

    def test_unknown_effect_is_preserved_then_reconciled(self):
        provider = Provider(charge_error=TimeoutError("ambiguous"))
        first = payment.submit(self.store, provider, "op_1", "tenant_A", 123)
        duplicate = payment.submit(self.store, provider, "op_1", "tenant_A", 123)
        self.assertEqual((first.status, first.receipt), ("pending", None))
        self.assertEqual(duplicate, first)
        final = payment.reconcile(self.store, provider, "op_1", "tenant_A", 123)
        self.assertEqual(final.status, "completed")
        self.assertEqual(final.receipt, next(iter(provider.receipts.values())))
        self.assertEqual(len(provider.calls), 1)

    def test_missing_and_failed_lookup_never_resubmit(self):
        provider = Provider(charge_error=ConnectionError("ambiguous"))
        payment.submit(self.store, provider, "op_1", "tenant_A", 123)
        provider.receipts.clear()
        result = payment.reconcile(self.store, provider, "op_1", "tenant_A", 123)
        self.assertEqual(result.status, "pending")
        provider.lookup_error = TimeoutError("unavailable")
        result = payment.reconcile(self.store, provider, "op_1", "tenant_A", 123)
        self.assertEqual(result.status, "pending")
        self.assertEqual(len(provider.calls), 1)

    def test_payload_and_tenant_are_bound_before_any_provider_call(self):
        provider = Provider(charge_error=TimeoutError("ambiguous"))
        payment.submit(self.store, provider, "op_1", "tenant_A", 123)
        for operation in (payment.submit, payment.reconcile):
            for tenant, amount in (("tenant_B", 123), ("tenant_A", 124)):
                with self.subTest(operation=operation.__name__, tenant=tenant, amount=amount):
                    with self.assertRaises(ValueError):
                        operation(self.store, provider, "op_1", tenant, amount)
        self.assertEqual(len(provider.calls), 1)

    def test_invalid_input_has_no_effect(self):
        provider = Provider()
        invalid = [("", "tenant", 1), (None, "tenant", 1), ("x" * 65, "tenant", 1),
                   ("op", "../tenant", 1), ("op", "tenant", True), ("op", "tenant", 0),
                   ("op", "tenant", -1), ("op", "tenant", 100_000_001),
                   ("op", "tenant", 1.5), ("op", None, 1)]
        for operation in (payment.submit, payment.reconcile):
            for args in invalid:
                with self.subTest(operation=operation.__name__, args=args):
                    with self.assertRaises(ValueError):
                        operation(self.store, provider, *args)
        self.assertEqual(provider.calls, [])

    def test_unexpected_exception_propagates_without_forgetting_operation(self):
        provider = Provider(charge_error=RuntimeError("unexpected"))
        with self.assertRaises(RuntimeError):
            payment.submit(self.store, provider, "op_1", "tenant_A", 123)
        again = payment.submit(self.store, provider, "op_1", "tenant_A", 123)
        self.assertEqual(again.status, "pending")
        self.assertEqual(len(provider.calls), 1)

    def test_duplicate_and_unrelated_work_are_not_blocked_by_provider(self):
        entered = threading.Event()
        release = threading.Event()
        original = Provider()
        outcomes = []
        errors = []

        class Slow(Provider):
            def charge(self, key, amount_cents):
                entered.set()
                if not release.wait(3):
                    raise TimeoutError("grader released stalled worker")
                return original.charge(key, amount_cents)

        def invoke(provider, operation):
            try:
                outcomes.append(payment.submit(self.store, provider, operation, "tenant_A", 123))
            except BaseException as exc:
                errors.append(exc)

        worker = threading.Thread(target=invoke, args=(Slow(), "slow"), daemon=True)
        workers = [worker]
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            duplicate = threading.Thread(target=invoke, args=(original, "slow"), daemon=True)
            unrelated = threading.Thread(target=invoke, args=(original, "other"), daemon=True)
            workers.extend((duplicate, unrelated))
            duplicate.start()
            unrelated.start()
            duplicate.join(1)
            unrelated.join(1)
            self.assertFalse(duplicate.is_alive(), "duplicate should observe pending state")
            self.assertFalse(unrelated.is_alive(), "provider must not hold the global store lock")
        finally:
            release.set()
            for running in workers:
                running.join(2)
        self.assertTrue(all(not running.is_alive() for running in workers))
        self.assertEqual(errors, [])
        self.assertEqual(sum(amount == 123 for _, amount in original.calls), 2)
        self.assertEqual(sorted(result.status for result in outcomes), ["completed", "completed", "pending"])


if __name__ == "__main__":
    unittest.main()
