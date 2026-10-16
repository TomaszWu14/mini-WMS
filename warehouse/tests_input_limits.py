"""US-002 / R3: limity liczby palet i ilości w przyjęciu (formularz, serwis, import)."""

from django.contrib.auth.models import User
from django.test import TestCase

from . import services
from .models import (
    HandlingUnit,
    HUNumberingConfig,
    Material,
    Profile,
    Role,
    StockMovement,
    Unit,
)
from .receipt_import import import_receipts


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("op", password="OpPass123!")
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        unit = Unit.objects.get_or_create(code="PCS")[0]
        self.material = Material.objects.create(index="MAT-L", name="Limit", unit=unit)
        self.client.login(username="op", password="OpPass123!")

    def _next_number(self):
        cfg = HUNumberingConfig.objects.order_by("pk").first()
        return cfg.next_number if cfg else None

    def _post_receive(self, total, pallets):
        return self.client.post(
            "/przyjecie/",
            {
                "material": self.material.pk,
                "mode": "total",
                "total_quantity": total,
                "pallets": pallets,
            },
        )


class ReceiveFormLimitTests(_Base):
    def test_too_many_pallets_rejected_without_writes(self):
        before = self._next_number()
        resp = self._post_receive(
            services.MAX_PALLETS_PER_RECEIPT + 1, services.MAX_PALLETS_PER_RECEIPT + 1
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, str(services.MAX_PALLETS_PER_RECEIPT))
        self.assertEqual(HandlingUnit.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(self._next_number(), before)

    def test_boundary_pallets_accepted(self):
        n = services.MAX_PALLETS_PER_RECEIPT
        resp = self._post_receive(n, n)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(HandlingUnit.objects.count(), n)
        self.assertEqual(StockMovement.objects.count(), n)

    def test_too_large_quantity_rejected(self):
        resp = self._post_receive(services.MAX_RECEIPT_QUANTITY + 1, 1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(HandlingUnit.objects.count(), 0)

    def test_per_pallet_mode_total_over_limit_rejected(self):
        resp = self.client.post(
            "/przyjecie/",
            {
                "material": self.material.pk,
                "mode": "per_pallet",
                "qty_per_pallet": services.MAX_RECEIPT_QUANTITY,
                "pallets": 2,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(HandlingUnit.objects.count(), 0)

    def test_viewer_still_forbidden(self):
        Profile.objects.filter(user=self.user).update(role=Role.VIEWER)
        resp = self._post_receive(10, 1)
        self.assertEqual(resp.status_code, 403)


class ServiceLimitTests(_Base):
    def test_split_quantity_refuses_too_many_pallets_before_allocating(self):
        with self.assertRaises(services.WMSError):
            services.split_quantity(10**7, services.MAX_PALLETS_PER_RECEIPT + 1)

    def test_receive_material_refuses_without_consuming_numbers(self):
        before = self._next_number()
        with self.assertRaises(services.WMSError):
            services.receive_material(
                material=self.material,
                quantities=[1] * (services.MAX_PALLETS_PER_RECEIPT + 1),
                user=self.user,
            )
        with self.assertRaises(services.WMSError):
            services.receive_material(
                material=self.material,
                quantities=[services.MAX_RECEIPT_QUANTITY + 1],
                user=self.user,
            )
        self.assertEqual(HandlingUnit.objects.count(), 0)
        self.assertEqual(self._next_number(), before)


def _csv(rows):
    lines = ["indeks;ilosc;palety"] + [";".join(map(str, r)) for r in rows]
    return ("\n".join(lines) + "\n").encode()


class ReceiptImportLimitTests(_Base):
    def test_row_over_pallet_limit_skipped_others_imported(self):
        data = _csv(
            [("MAT-L", 10, 2), ("MAT-L", 10**6, services.MAX_PALLETS_PER_RECEIPT + 1)]
        )
        result = import_receipts("p.csv", data, self.user)
        self.assertEqual(result["created_hus"], 2)
        self.assertTrue(any("Wiersz 3" in e for e in result["errors"]))
        self.assertEqual(HandlingUnit.objects.count(), 2)

    def test_file_over_total_pallet_limit_rejected_before_any_write(self):
        per_row = services.MAX_PALLETS_PER_RECEIPT
        rows_needed = services.MAX_HU_PER_IMPORT // per_row + 1
        data = _csv([("MAT-L", per_row, per_row)] * rows_needed)
        before = self._next_number()
        result = import_receipts("p.csv", data, self.user)
        self.assertEqual(result["created_hus"], 0)
        self.assertTrue(
            any(str(services.MAX_HU_PER_IMPORT) in e for e in result["errors"])
        )
        self.assertEqual(HandlingUnit.objects.count(), 0)
        self.assertEqual(self._next_number(), before)

    def test_overflowing_number_reported_not_500(self):
        data = _csv([("MAT-L", "1e999", 1), ("MAT-L", 5, 1)])
        result = import_receipts("p.csv", data, self.user)
        self.assertEqual(result["created_hus"], 1)
        self.assertTrue(any("Wiersz 2" in e for e in result["errors"]))
