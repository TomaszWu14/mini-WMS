"""Współbieżność realizacji WZ — tylko na PostgreSQL (SQLite nie blokuje wierszy).

Lokalnie: DATABASE_URL=postgres://… python manage.py test warehouse.tests_concurrency_pg
W CI uruchamia go job `test-postgres`.
"""

import threading
import time
import unittest

from django.contrib.auth.models import User
from django.db import connection, connections, transaction
from django.test import TransactionTestCase

from . import services
from .models import (
    HandlingUnit,
    HUStatus,
    IssueDocument,
    IssueLine,
    IssueStatus,
    Material,
    StockMovement,
    Unit,
)
from .services import WMSError


@unittest.skipUnless(connection.vendor == "postgresql", "wymaga PostgreSQL")
class ConcurrentIssueTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user("op", password="x")
        unit = Unit.objects.get_or_create(code="PCS")[0]
        self.material = Material.objects.create(index="MAT-C", name="C", unit=unit)
        self.hu = HandlingUnit.objects.create(
            number="HU-C1",
            material=self.material,
            quantity=10,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def _doc(self, number, qty):
        doc = IssueDocument.objects.create(number=number, created_by=self.user)
        IssueLine.objects.create(
            document=doc, material=self.material, requested_qty=qty
        )
        return doc

    def _run_while_locked(self, locked_qs, docs):
        """Realizuje dokumenty równolegle, gdy wiersz z `locked_qs` jest zablokowany.

        Wątek blokujący trzyma `SELECT … FOR UPDATE`, aż oba wątki realizacji
        staną na tej blokadzie — to wymusza wyścig zamiast liczyć na przypadek.
        """
        locked, release = threading.Event(), threading.Event()
        results: list[str] = []

        def holder():
            try:
                with transaction.atomic():
                    locked_qs.select_for_update().get()
                    locked.set()
                    release.wait(10)
            finally:
                connections.close_all()

        def worker(doc):
            try:
                services.execute_issue_document(document=doc, user=self.user)
                results.append("ok")
            except WMSError as exc:
                results.append(str(exc))
            finally:
                connections.close_all()

        h = threading.Thread(target=holder)
        h.start()
        locked.wait(10)
        workers = [threading.Thread(target=worker, args=(d,)) for d in docs]
        for w in workers:
            w.start()
        # Celowe opóźnienie: oba wątki mają już czekać na blokadę palety (test wyścigu).
        time.sleep(1)  # nosemgrep
        release.set()
        for t in [h, *workers]:
            t.join(15)
            self.assertFalse(t.is_alive(), "wątek zawisł na blokadzie")
        return results

    def test_two_documents_cannot_oversell_one_pallet(self):
        a, b = self._doc("WZ-A", 8), self._doc("WZ-B", 8)
        # Blokada palety: oba wątki przeszły już sprawdzenie dostępności bez blokady.
        locked = HandlingUnit.objects.filter(pk=self.hu.pk)
        results = self._run_while_locked(locked, [a, b])

        self.assertEqual(results.count("ok"), 1, results)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 2)
        self.assertEqual(StockMovement.objects.filter(quantity_delta=-8).count(), 1)

    def test_same_document_executed_twice_issues_once(self):
        doc = self._doc("WZ-X", 4)
        # Blokada dokumentu: oba wątki mają w Pythonie dokument jako „Otwarty”.
        locked = IssueDocument.objects.filter(pk=doc.pk)
        results = self._run_while_locked(locked, [doc, doc])

        self.assertEqual(results.count("ok"), 1, results)
        doc.refresh_from_db()
        self.assertEqual(doc.status, IssueStatus.ZREALIZOWANY)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 6)

    def test_scanner_pick_and_execute_on_same_document(self):
        """US-018 kryterium 3: skaner (pobranie + domknięcie) i „Realizuj” równolegle."""
        doc = self._doc("WZ-S", 4)
        line = doc.lines.get()
        locked, release = threading.Event(), threading.Event()
        results: list[str] = []

        def holder():
            try:
                with transaction.atomic():
                    IssueDocument.objects.select_for_update().get(pk=doc.pk)
                    IssueLine.objects.select_for_update().get(pk=line.pk)
                    locked.set()
                    release.wait(10)
            finally:
                connections.close_all()

        def scanner():
            try:
                services.pick_from_hu(
                    hu=self.hu, quantity=4, user=self.user, document=doc, line=line
                )
                services.complete_if_picked(doc)
                results.append("scanner-ok")
            except WMSError as exc:
                results.append(str(exc))
            finally:
                connections.close_all()

        def panel():
            try:
                services.execute_issue_document(document=doc, user=self.user)
                results.append("panel-ok")
            except WMSError as exc:
                results.append(str(exc))
            finally:
                connections.close_all()

        h = threading.Thread(target=holder)
        h.start()
        locked.wait(10)
        workers = [threading.Thread(target=scanner), threading.Thread(target=panel)]
        for w in workers:
            w.start()
        time.sleep(1)  # nosemgrep — oba wątki czekają na blokadę
        release.set()
        for t in [h, *workers]:
            t.join(15)
            self.assertFalse(t.is_alive(), "wątek zawisł na blokadzie")

        line.refresh_from_db()
        doc.refresh_from_db()
        self.assertEqual(line.picked_qty, 4, results)
        self.assertEqual(doc.status, IssueStatus.ZREALIZOWANY)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 6)
        self.assertEqual(
            sum(
                m.quantity_delta
                for m in StockMovement.objects.filter(issue_document=doc)
            ),
            -4,
        )

    def _race(self, holder_body, waiter_body):
        """Wątek A trzyma blokadę dokumentu i wykonuje `holder_body`; B czeka na nią."""
        locked, release = threading.Event(), threading.Event()
        results: list[str] = []

        waited: list[float] = []

        def holder():
            try:
                with transaction.atomic():
                    holder_body()
                    locked.set()
                    release.wait(10)
            except Exception as exc:  # noqa: BLE001 — przyczyna widoczna w asercji
                results.append(f"holder:{type(exc).__name__}:{exc}")
                locked.set()
            finally:
                connections.close_all()

        def waiter():
            start = time.monotonic()
            try:
                waiter_body()
                results.append("ok")
            except WMSError as exc:
                results.append(str(exc))
            except Exception as exc:  # noqa: BLE001 — test ma pokazać 500 jako porażkę
                results.append(f"500:{type(exc).__name__}")
            finally:
                waited.append(time.monotonic() - start)
                connections.close_all()

        h = threading.Thread(target=holder)
        h.start()
        locked.wait(10)
        w = threading.Thread(target=waiter)
        w.start()
        time.sleep(1)  # nosemgrep — B czeka na blokadę dokumentu
        release.set()
        for t in (h, w):
            t.join(15)
            self.assertFalse(t.is_alive(), "wątek zawisł na blokadzie")
        # Przegląd [DB] US-052: B musiał czekać na blokadę A (inaczej test nie dowodzi wyścigu).
        self.assertGreaterEqual(
            waited[0], 0.9, f"wątek B nie czekał na blokadę: {results}"
        )
        return results

    def test_add_line_while_document_is_being_closed(self):
        """US-052 kryterium 1: dodanie pozycji w trakcie „Realizuj” → odmowa, bez nowej pozycji."""
        doc = self._doc("WZ-AL", 2)
        stale = IssueDocument.objects.get(pk=doc.pk)

        def close():
            services.execute_issue_document(document=doc, user=self.user)

        def add():
            services.add_issue_line(
                document=stale, material=self.material, requested_qty=1
            )

        results = self._race(close, add)
        self.assertEqual(len(results), 1)
        self.assertIn("tylko w otwartym", results[0])
        doc.refresh_from_db()
        self.assertEqual(doc.status, IssueStatus.ZREALIZOWANY)
        self.assertEqual(doc.lines.count(), 1)

    def test_pick_while_line_is_being_deleted(self):
        """US-052 kryterium 2: skaner czeka na usuwaną pozycję → komunikat, nie 500."""
        doc = self._doc("WZ-DL", 2)
        line = doc.lines.get()

        def delete():
            services.delete_issue_line(document=doc, line_id=line.pk)

        def pick():
            services.pick_from_hu(
                hu=self.hu, quantity=1, user=self.user, document=doc, line=line
            )

        results = self._race(delete, pick)
        self.assertEqual(len(results), 1)
        self.assertIn("usunięta", results[0])
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 10)
