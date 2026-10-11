"""Testy łatek skanera: specific_hu w pickingu (W-25), ostrzeżenie FEFO (W-11),
wymagane zlecenie (N9) i powód korekty w inwentaryzacji (W-26), ostrzeżenie o
przekroczeniu pojemności przy alokacji (W-08)."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from . import services
from .models import (
    AdjustReason,
    HandlingUnit,
    HUStatus,
    IssueDocument,
    IssueLine,
    IssueStatus,
    Location,
    LocationType,
    Material,
    MovementType,
    Profile,
    Role,
    StockMovement,
    Unit,
)


class ScannerFixesBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operator", password="x")
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        self.unit = Unit.objects.get_or_create(code="PCS")[0]
        self.material = Material.objects.create(
            index="MAT-SC", name="Materiał skanera", unit=self.unit
        )

    def _hu(self, number, quantity=5, expiry=None):
        return HandlingUnit.objects.create(
            number=number,
            material=self.material,
            quantity=quantity,
            status=HUStatus.ZMAGAZYNOWANY,
            expiry_date=expiry,
        )

    def _doc(self):
        return IssueDocument.objects.create(
            number=services.generate_issue_number(),
            status=IssueStatus.OTWARTY,
            created_by=self.user,
        )


class ApiPickSpecificHuTests(ScannerFixesBase):
    def test_other_pallet_rejected_when_line_bound(self):
        bound = self._hu("HU-BOUND-1")
        other = self._hu("HU-OTHER-1")
        doc = self._doc()
        IssueLine.objects.create(
            document=doc, material=self.material, requested_qty=5, specific_hu=bound
        )
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": other.number, "quantity": "1", "document": doc.id},
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertIn("HU-BOUND-1", data["error"])
        self.assertIn("zeskanuj", data["error"])

    def test_bound_pallet_accepted(self):
        bound = self._hu("HU-BOUND-2")
        doc = self._doc()
        IssueLine.objects.create(
            document=doc, material=self.material, requested_qty=5, specific_hu=bound
        )
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": bound.number, "quantity": "2", "document": doc.id},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        bound.refresh_from_db()
        self.assertEqual(bound.quantity, 3)

    def test_unbound_line_still_works(self):
        hu = self._hu("HU-UNBOUND-1")
        doc = self._doc()
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=5)
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": hu.number, "quantity": "1", "document": doc.id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])


class ApiPickFefoWarningTests(ScannerFixesBase):
    def test_warning_present_when_skipping_fefo_order(self):
        self._hu("HU-EARLY-1", expiry=date.today() + timedelta(days=5))
        late = self._hu("HU-LATE-1", expiry=date.today() + timedelta(days=30))
        doc = self._doc()
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=10)
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": late.number, "quantity": "1", "document": doc.id},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("warning", data)
        self.assertIn("HU-EARLY-1", data["warning"])

    def test_warning_absent_when_following_fefo_order(self):
        early = self._hu("HU-EARLY-2", expiry=date.today() + timedelta(days=5))
        self._hu("HU-LATE-2", expiry=date.today() + timedelta(days=30))
        doc = self._doc()
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=10)
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": early.number, "quantity": "1", "document": doc.id},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertNotIn("warning", data)


class ApiPickDocumentRequiredTests(ScannerFixesBase):
    def test_pick_without_document_rejected(self):
        hu = self._hu("HU-NODOC-1")
        resp = self.client.post("/skaner/api/pick/", {"hu": hu.number, "quantity": "1"})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "Brak zlecenia.")


class ApiInventoryReasonTests(ScannerFixesBase):
    def test_inventory_without_reason_rejected(self):
        hu = self._hu("HU-INV-1", quantity=10)
        resp = self.client.post(
            "/skaner/api/inwentaryzacja/", {"hu": hu.number, "delta": "3"}
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "Wybierz powód korekty.")
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 10)

    def test_inventory_with_reason_creates_correction(self):
        hu = self._hu("HU-INV-2", quantity=10)
        resp = self.client.post(
            "/skaner/api/inwentaryzacja/",
            {"hu": hu.number, "delta": "-3", "reason": AdjustReason.STRATA},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 7)
        move = StockMovement.objects.filter(
            handling_unit=hu, type=MovementType.KOREKTA
        ).first()
        self.assertIsNotNone(move)
        self.assertEqual(move.reason, AdjustReason.STRATA)


class ApiAllocateCapacityWarningTests(ScannerFixesBase):
    def test_allocate_over_capacity_warns_but_succeeds(self):
        loc = Location.objects.create(
            code="LOC-CAP-1", type=LocationType.ZAPAS, capacity=1
        )
        already = self._hu("HU-CAP-0")
        services.allocate_hu(hu=already, location=loc, user=self.user)

        hu = self._hu("HU-CAP-1")
        resp = self.client.post(
            "/skaner/api/rozmiesc/", {"hu": hu.number, "location": loc.code}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("warning", data)
        self.assertIn("LOC-CAP-1", data["warning"])
