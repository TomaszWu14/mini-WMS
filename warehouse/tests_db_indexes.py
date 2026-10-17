"""US-051: indeks dziennika logowań — migracja odwracalna, plan zapytania retencji."""

import unittest
from datetime import timedelta

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from .models import LoginEvent

INDEX = "loginevent_created_idx"


def _index_names():
    with connection.cursor() as cur:
        constraints = connection.introspection.get_constraints(
            cur, LoginEvent._meta.db_table
        )
    return {name for name, c in constraints.items() if c["index"]}


class LoginEventIndexMigrationTests(TransactionTestCase):
    def test_migration_adds_and_removes_index(self):
        """Kryterium 1: `AddIndex` w repo i odwracalny (0012 ↔ 0011)."""
        self.assertIn(INDEX, _index_names())
        executor = MigrationExecutor(connection)
        executor.migrate([("warehouse", "0011_auditevent")])
        self.assertNotIn(INDEX, _index_names())
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes("warehouse"))
        self.assertIn(INDEX, _index_names())


@unittest.skipUnless(connection.vendor == "postgresql", "wymaga PostgreSQL")
class LoginEventIndexPlanTests(TestCase):
    def test_purge_query_uses_index(self):
        """Kryterium 2: `purge_login_events` (created_at < cutoff) może iść indeksem."""
        now = timezone.now()
        LoginEvent.objects.bulk_create(
            LoginEvent(
                username=f"u{i}",
                kind=LoginEvent.Kind.LOGIN,
                created_at=now - timedelta(days=i),
            )
            for i in range(200)
        )
        cutoff = now - timedelta(days=90)
        qs = LoginEvent.objects.filter(created_at__lt=cutoff)
        with transaction.atomic(), connection.cursor() as cur:
            cur.execute("ANALYZE warehouse_loginevent")
            # Mała tabela w teście: planista wolałby seq scan — wyłączamy go lokalnie,
            # żeby sprawdzić, że indeks pasuje do warunku (nie że jest „tańszy”).
            cur.execute("SET LOCAL enable_seqscan = off")
            self.assertIn(INDEX, qs.explain())
            self.assertIn(INDEX, LoginEvent.objects.all()[:100].explain())
