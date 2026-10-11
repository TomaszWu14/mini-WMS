"""Testy wycinka: wymagany powód korekty, ostrzeżenie o pojemności, przegięcie
pozycji WZ, raport „bez limitu”, strona 403, widoczność linku do /admin/,
linki powrotu, ostrzeżenie o pominiętych wartościach w spisie."""

from django.contrib.auth.models import User
from django.test import TestCase

from . import services
from .models import (
    AdjustReason,
    HandlingUnit,
    HUStatus,
    IssueDocument,
    IssueLine,
    Location,
    LocationType,
    Material,
    MovementType,
    Profile,
    Role,
    StockMovement,
    StocktakeSheet,
    Unit,
)


class BaseSetup(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operator", password="x")
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.unit = Unit.objects.get_or_create(code="PCS")[0]
        self.material = Material.objects.create(
            index="MAT-1", name="Materiał testowy", unit=self.unit
        )


class HUCorrectionReasonTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.client.login(username="operator", password="x")
        self.hu = HandlingUnit.objects.create(
            number="HU-COR-1",
            material=self.material,
            quantity=10,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def test_correction_without_reason_rejected(self):
        resp = self.client.post(f"/hu/{self.hu.pk}/korekta/", {"new_quantity": "7"})
        self.assertEqual(resp.status_code, 200)  # formularz z błędem, brak redirectu
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 10)

    def test_correction_with_reason_creates_korekta_with_reason(self):
        resp = self.client.post(
            f"/hu/{self.hu.pk}/korekta/",
            {"new_quantity": "7", "reason": AdjustReason.STRATA},
        )
        self.assertEqual(resp.status_code, 302)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 7)
        move = StockMovement.objects.filter(
            type=MovementType.KOREKTA, handling_unit=self.hu
        ).first()
        self.assertIsNotNone(move)
        self.assertEqual(move.reason, AdjustReason.STRATA)


class WebInventoryReasonTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.client.login(username="operator", password="x")
        self.hu = HandlingUnit.objects.create(
            number="INV-R1",
            material=self.material,
            quantity=10,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def test_inventory_without_reason_rejected(self):
        resp = self.client.post(
            "/inwentaryzacja/",
            {"hu_number": "INV-R1", "mode": "add", "quantity": "5"},
        )
        self.assertEqual(resp.status_code, 200)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 10)

    def test_inventory_with_reason_uses_adjust_hu_quantity(self):
        resp = self.client.post(
            "/inwentaryzacja/",
            {
                "hu_number": "INV-R1",
                "mode": "add",
                "quantity": "5",
                "reason": AdjustReason.NADWYZKA,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 15)
        move = StockMovement.objects.filter(
            type=MovementType.KOREKTA, handling_unit=self.hu
        ).first()
        self.assertEqual(move.reason, AdjustReason.NADWYZKA)


class AllocateCapacityWarningTests(BaseSetup):
    def test_over_capacity_allocation_succeeds_with_warning(self):
        self.client.login(username="operator", password="x")
        loc = Location.objects.create(
            code="L-FULL", type=LocationType.ZAPAS, capacity=1
        )
        hu1 = services.receive_material(
            material=self.material, quantities=[1], user=self.user
        ).handling_units[0]
        services.allocate_hu(hu=hu1, location=loc, user=self.user)
        hu2 = services.receive_material(
            material=self.material, quantities=[1], user=self.user
        ).handling_units[0]

        resp = self.client.post(
            f"/hu/{hu2.pk}/alokacja/", {"location": loc.pk}, follow=True
        )
        self.assertEqual(resp.status_code, 200)
        hu2.refresh_from_db()
        self.assertEqual(hu2.location_id, loc.pk)
        messages = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("pojemność" in m for m in messages))


class IssueAddLineOvercommitTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.client.login(username="operator", password="x")
        self.hu = HandlingUnit.objects.create(
            number="HU-OC-1",
            material=self.material,
            quantity=10,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        self.doc = IssueDocument.objects.create(number="WZ-OC-1")
        IssueLine.objects.create(
            document=self.doc,
            material=self.material,
            requested_qty=7,
            specific_hu=self.hu,
        )

    def test_overcommit_rejected(self):
        resp = self.client.post(
            f"/wydania/{self.doc.pk}/pozycja/",
            {
                "mode": "hu",
                "specific_hu": self.hu.pk,
                "requested_qty": "5",  # 7 + 5 > 10 dostępnych na HU
            },
            follow=True,
        )
        self.assertEqual(self.doc.lines.count(), 1)  # nie dodano drugiej pozycji
        messages = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("ma tylko" in m for m in messages))

    def test_within_capacity_accepted(self):
        self.client.post(
            f"/wydania/{self.doc.pk}/pozycja/",
            {"mode": "hu", "specific_hu": self.hu.pk, "requested_qty": "3"},
        )
        self.assertEqual(self.doc.lines.count(), 2)


class ReportLocationsNoLimitTests(BaseSetup):
    def test_capacity_zero_shows_bez_limitu_not_pelna(self):
        Location.objects.create(code="L-NOLIM", type=LocationType.ZAPAS, capacity=0)
        HandlingUnit.objects.create(
            number="HU-NL-1",
            material=self.material,
            quantity=3,
            location=Location.objects.get(code="L-NOLIM"),
            status=HUStatus.ZMAGAZYNOWANY,
        )
        self.client.login(username="operator", password="x")
        resp = self.client.get("/raporty/lokalizacje/")
        self.assertContains(resp, "bez limitu")
        self.assertNotContains(resp, "pełna")
        self.assertContains(resp, "zajęta")


class PermissionDeniedPageTests(BaseSetup):
    def test_viewer_gets_403_with_menu(self):
        Profile.objects.filter(user=self.user).update(role=Role.VIEWER)
        self.client.login(username="operator", password="x")
        resp = self.client.get("/przyjecie/")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "Brak uprawnień", status_code=403)
        self.assertContains(resp, "Pulpit", status_code=403)


class AdminLinkVisibilityTests(BaseSetup):
    def test_viewer_dashboard_lacks_issue_import(self):
        Profile.objects.filter(user=self.user).update(role=Role.VIEWER)
        self.client.login(username="operator", password="x")
        resp = self.client.get("/")
        self.assertNotContains(resp, "/wydania/import/")

    def test_operator_without_superuser_has_no_admin_link(self):
        self.client.login(username="operator", password="x")
        resp = self.client.get("/")
        self.assertNotContains(resp, 'href="/admin/"')

    def test_superuser_sees_admin_link(self):
        User.objects.create_superuser("boss", password="x", email="b@example.com")
        self.client.login(username="boss", password="x")
        resp = self.client.get("/")
        self.assertContains(resp, 'href="/admin/"')


class BackLinkTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.client.login(username="operator", password="x")

    def test_hu_detail_has_back_link(self):
        hu = HandlingUnit.objects.create(
            number="HU-BL-1",
            material=self.material,
            quantity=1,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        resp = self.client.get(f"/hu/{hu.pk}/")
        self.assertContains(resp, 'href="/hu/"')

    def test_issue_detail_has_back_link(self):
        doc = IssueDocument.objects.create(number="WZ-BL-1")
        resp = self.client.get(f"/wydania/{doc.pk}/")
        self.assertContains(resp, 'href="/wydania/"')

    def test_stocktake_detail_has_back_link(self):
        sheet = StocktakeSheet.objects.create(number="SP-BL-1", created_by=self.user)
        resp = self.client.get(f"/spis/{sheet.pk}/")
        self.assertContains(resp, 'href="/spis/"')

    def test_receive_has_cancel_link(self):
        resp = self.client.get("/przyjecie/")
        self.assertContains(resp, 'href="/hu/"')
        self.assertContains(resp, "Anuluj")


class StocktakeSaveWarnsTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.client.login(username="operator", password="x")
        self.loc = Location.objects.create(code="L-SP1", type=LocationType.ZAPAS)
        self.hu = HandlingUnit.objects.create(
            number="HU-SP-1",
            material=self.material,
            quantity=10,
            location=self.loc,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        self.sheet = services.create_stocktake(location=self.loc, user=self.user)

    def test_non_numeric_value_triggers_warning(self):
        line = self.sheet.lines.first()
        resp = self.client.post(
            f"/spis/{self.sheet.pk}/zapisz/",
            {f"counted_{line.id}": "abc"},
            follow=True,
        )
        messages = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("Pominięto" in m for m in messages))
        line.refresh_from_db()
        self.assertIsNone(line.counted_qty)
