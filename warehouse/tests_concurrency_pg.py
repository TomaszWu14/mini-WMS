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
        time.sleep(1)  # oba wątki czekają już na blokadę palety
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
