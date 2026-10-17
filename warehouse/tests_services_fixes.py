"""Testy poprawek services.py: split_quantity, W-08 (pojemność informacyjna),
blokada wiersza przy execute_issue_document/correct_hu_quantity, adjust_hu_quantity,
first_pickable_hu."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from . import services
from .forms import ReceiveForm
from .models import (
    HandlingUnit,
    HUStatus,
    IssueDocument,
    IssueLine,
    IssueStatus,
    Location,
    LocationType,
    Material,
    MovementType,
    StockMovement,
    Unit,
)
from .services import WMSError


class BaseSetup(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operator2", password="x")
        self.unit = Unit.objects.get_or_create(code="PCS")[0]
        self.material = Material.objects.create(
            index="MAT-FIX", name="Materiał testowy", unit=self.unit
        )


class SplitQuantityRemainderTests(TestCase):
    def test_10_on_4_pallets_spreads_remainder(self):
        self.assertEqual(services.split_quantity(10, 4), [2, 2, 3, 3])

    def test_100_on_3_pallets_unchanged(self):
        self.assertEqual(services.split_quantity(100, 3), [33, 33, 34])


class ReceiveFormMatchesSplitTests(BaseSetup):
    def test_receive_10_on_4_pallets_with_max_3_succeeds(self):
        """Bug: forms.py liczy najgęściej obciążoną paletę jako ceil(10/4)=3,
        formularz przepuszczał, ale stary split_quantity dawał [2,2,2,4] i
        zapis padał. Nowy split musi być zgodny z walidacją formularza."""
        self.material.max_per_pallet = 3
        self.material.save()
        form = ReceiveForm(
            data={
                "material": self.material.pk,
                "mode": ReceiveForm.MODE_TOTAL,
                "total_quantity": 10,
                "pallets": 4,
                "lot": "",
                "expiry_date": "",
                "delivery_ref": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        quantities = services.split_quantity(
            form.cleaned_data["computed_total"], form.cleaned_data["pallets"]
        )
        self.assertEqual(max(quantities), 3)
        result = services.receive_material(
            material=self.material, quantities=quantities, user=self.user
        )
        self.assertEqual(sum(hu.quantity for hu in result.handling_units), 10)


class LocationOverCapacityTests(BaseSetup):
    def test_allocate_over_capacity_succeeds(self):
        loc = Location.objects.create(code="OC-1", type=LocationType.ZAPAS, capacity=1)
        hu1 = services.receive_material(
            material=self.material, quantities=[5], user=self.user
        ).handling_units[0]
        hu2 = services.receive_material(
            material=self.material, quantities=[5], user=self.user
        ).handling_units[0]
        services.allocate_hu(hu=hu1, location=loc, user=self.user)
        services.allocate_hu(hu=hu2, location=loc, user=self.user)
        hu2.refresh_from_db()
        self.assertEqual(hu2.location, loc)

    def test_location_over_capacity_true_when_exceeded(self):
        loc = Location.objects.create(code="OC-2", type=LocationType.ZAPAS, capacity=1)
        hu1 = services.receive_material(
            material=self.material, quantities=[5], user=self.user
        ).handling_units[0]
        hu2 = services.receive_material(
            material=self.material, quantities=[5], user=self.user
        ).handling_units[0]
        services.allocate_hu(hu=hu1, location=loc, user=self.user)
        self.assertFalse(services.location_over_capacity(loc))
        services.allocate_hu(hu=hu2, location=loc, user=self.user)
        self.assertTrue(services.location_over_capacity(loc))

    def test_location_over_capacity_false_under_limit(self):
        loc = Location.objects.create(code="OC-3", type=LocationType.ZAPAS, capacity=5)
        hu = services.receive_material(
            material=self.material, quantities=[5], user=self.user
        ).handling_units[0]
        services.allocate_hu(hu=hu, location=loc, user=self.user)
        self.assertFalse(services.location_over_capacity(loc))

    def test_location_over_capacity_never_true_when_capacity_zero(self):
        loc = Location.objects.create(code="OC-4", type=LocationType.ZAPAS, capacity=0)
        for _ in range(5):
            hu = services.receive_material(
                material=self.material, quantities=[1], user=self.user
            ).handling_units[0]
            services.allocate_hu(hu=hu, location=loc, user=self.user)
        self.assertFalse(services.location_over_capacity(loc))


class ExecuteIssueDocumentDoubleClickTests(BaseSetup):
    def test_second_execute_raises_even_with_stale_python_object(self):
        loc = Location.objects.create(code="DX-1", type=LocationType.PICKING)
        HandlingUnit.objects.create(
            number=services.generate_hu_number(),
            material=self.material,
            quantity=20,
            location=loc,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=5)

        # Symulacja: operator ma w pamięci stary obiekt ze statusem OTWARTY.
        stale = IssueDocument.objects.get(pk=doc.pk)
        services.execute_issue_document(document=doc, user=self.user)
        self.assertEqual(stale.status, IssueStatus.OTWARTY)

        with self.assertRaises(WMSError):
            services.execute_issue_document(document=stale, user=self.user)


class AdjustHuQuantityTests(BaseSetup):
    def _hu(self, qty=10):
        return services.receive_material(
            material=self.material, quantities=[qty], user=self.user
        ).handling_units[0]

    def test_positive_delta_increases_quantity_and_logs_korekta(self):
        hu = self._hu(10)
        services.adjust_hu_quantity(hu=hu, delta=5, user=self.user, reason="POMYLKA")
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 15)
        self.assertTrue(
            StockMovement.objects.filter(
                handling_unit=hu, type=MovementType.KOREKTA, quantity_delta=5
            ).exists()
        )

    def test_negative_delta_decreases_quantity(self):
        hu = self._hu(10)
        services.adjust_hu_quantity(hu=hu, delta=-3, user=self.user, reason="POMYLKA")
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 7)

    def test_delta_below_zero_raises(self):
        hu = self._hu(2)
        with self.assertRaises(WMSError):
            services.adjust_hu_quantity(
                hu=hu, delta=-5, user=self.user, reason="POMYLKA"
            )

    def test_zero_delta_raises(self):
        hu = self._hu(10)
        with self.assertRaises(WMSError):
            services.adjust_hu_quantity(
                hu=hu, delta=0, user=self.user, reason="POMYLKA"
            )

    def test_delta_computed_from_locked_value_not_stale_object(self):
        hu = self._hu(10)
        stale = HandlingUnit.objects.get(pk=hu.pk)
        services.adjust_hu_quantity(
            hu=hu, delta=5, user=self.user, reason="POMYLKA"
        )  # -> 15
        services.adjust_hu_quantity(
            hu=stale, delta=2, user=self.user, reason="POMYLKA"
        )  # -> 17
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 17)


class FirstPickableHuTests(BaseSetup):
    def test_returns_earliest_expiry_picking_pallet(self):
        pick_loc = Location.objects.create(code="FP-1", type=LocationType.PICKING)
        sooner = HandlingUnit.objects.create(
            number=services.generate_hu_number(),
            material=self.material,
            quantity=5,
            location=pick_loc,
            expiry_date=date.today() + timedelta(days=5),
            status=HUStatus.ZMAGAZYNOWANY,
        )
        HandlingUnit.objects.create(
            number=services.generate_hu_number(),
            material=self.material,
            quantity=5,
            location=pick_loc,
            expiry_date=date.today() + timedelta(days=30),
            status=HUStatus.ZMAGAZYNOWANY,
        )
        self.assertEqual(services.first_pickable_hu(self.material).pk, sooner.pk)

    def test_returns_none_when_nothing_pickable(self):
        self.assertIsNone(services.first_pickable_hu(self.material))


class CorrectionReasonRequiredTests(BaseSetup):
    """W-26: każda korekta ma powód — pilnuje serwis, nie tylko formularz."""

    def test_correction_without_valid_reason_raises(self):
        hu = services.receive_material(
            material=self.material, quantities=[10], user=self.user
        ).handling_units[0]
        for bad in ("", "COKOLWIEK"):
            with self.assertRaises(WMSError):
                services.correct_hu_quantity(
                    hu=hu, new_quantity=7, user=self.user, reason=bad
                )
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 10)
        self.assertFalse(
            StockMovement.objects.filter(type=MovementType.KOREKTA).exists()
        )


class PickLineGuardTests(BaseSetup):
    """Pobranie na pozycję WZ nie przekroczy żądanej ilości ani nie trafi do
    zamkniętego dokumentu — osłona w `pick_from_hu` (skaner i „Realizuj”)."""

    def _doc_with_line(self, qty):
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        line = IssueLine.objects.create(
            document=doc, material=self.material, requested_qty=qty
        )
        hu = services.receive_material(
            material=self.material, quantities=[50], user=self.user
        ).handling_units[0]
        return doc, line, hu

    def test_pick_over_remaining_on_line_raises(self):
        doc, line, hu = self._doc_with_line(10)
        services.pick_from_hu(
            hu=hu, quantity=6, user=self.user, document=doc, line=line
        )
        with self.assertRaises(WMSError):
            services.pick_from_hu(
                hu=hu, quantity=5, user=self.user, document=doc, line=line
            )
        line.refresh_from_db()
        self.assertEqual(line.picked_qty, 6)

    def test_pick_on_closed_document_raises(self):
        doc, line, hu = self._doc_with_line(10)
        IssueDocument.objects.filter(pk=doc.pk).update(status=IssueStatus.ZREALIZOWANY)
        with self.assertRaises(WMSError):
            services.pick_from_hu(
                hu=hu, quantity=1, user=self.user, document=doc, line=line
            )
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 50)


class CompleteIfPickedTests(BaseSetup):
    """US-018: domknięcie WZ po ostatnim pobraniu — w serwisie, idempotentnie."""

    def _doc(self, qty=5):
        doc = IssueDocument.objects.create(number=f"WZ-C{qty}", created_by=self.user)
        line = IssueLine.objects.create(
            document=doc, material=self.material, requested_qty=qty
        )
        return doc, line

    def _hu(self, qty=10):
        return HandlingUnit.objects.create(
            number=f"HU-C{qty}",
            material=self.material,
            quantity=qty,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def test_closes_only_when_everything_picked(self):
        doc, line = self._doc(5)
        hu = self._hu()
        services.pick_from_hu(
            hu=hu, quantity=3, user=self.user, document=doc, line=line
        )
        self.assertFalse(services.complete_if_picked(doc))
        self.assertEqual(doc.status, IssueStatus.OTWARTY)
        services.pick_from_hu(
            hu=hu, quantity=2, user=self.user, document=doc, line=line
        )
        self.assertTrue(services.complete_if_picked(doc))
        doc.refresh_from_db()
        self.assertEqual(doc.status, IssueStatus.ZREALIZOWANY)
        self.assertIsNotNone(doc.completed_at)

    def test_idempotent_when_already_completed(self):
        """Kryterium 2: „Realizuj” zamknął dokument równolegle — bez podwójnego zamknięcia."""
        doc, _ = self._doc(4)
        self._hu()
        services.execute_issue_document(document=doc, user=self.user)
        doc.refresh_from_db()
        completed_at = doc.completed_at
        self.assertFalse(services.complete_if_picked(doc))
        doc.refresh_from_db()
        self.assertEqual(doc.status, IssueStatus.ZREALIZOWANY)
        self.assertEqual(doc.completed_at, completed_at)

    def test_stale_object_is_refreshed_under_lock(self):
        doc, line = self._doc(2)
        stale = IssueDocument.objects.get(pk=doc.pk)
        services.pick_from_hu(
            hu=self._hu(), quantity=2, user=self.user, document=doc, line=line
        )
        IssueDocument.objects.filter(pk=doc.pk).update(status=IssueStatus.SPAKOWANY)
        self.assertFalse(services.complete_if_picked(stale))
        self.assertEqual(stale.status, IssueStatus.SPAKOWANY)

    def test_document_without_lines_not_closed(self):
        doc = IssueDocument.objects.create(number="WZ-EMPTY", created_by=self.user)
        self.assertFalse(services.complete_if_picked(doc))

    def test_scanner_last_pick_closes_via_service(self):
        """Kryterium 1: API skanera nie ustawia statusu samo — woła serwis."""
        from unittest.mock import patch

        from .models import Profile, Role

        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.force_login(self.user)
        doc, _ = self._doc(3)
        hu = self._hu()
        with patch(
            "warehouse.scanner_views.services.complete_if_picked",
            wraps=services.complete_if_picked,
        ) as spy:
            resp = self.client.post(
                "/skaner/api/pick/",
                {"hu": hu.number, "quantity": "3", "document": str(doc.pk)},
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        spy.assert_called_once()
        self.assertTrue(resp.json()["document"]["completed"])
        doc.refresh_from_db()
        self.assertEqual(doc.status, IssueStatus.ZREALIZOWANY)

    def test_scanner_closes_fully_picked_open_document(self):
        """Przegląd [DB] US-018: WZ w pełni pobrany, ale otwarty (przerwane domknięcie)."""
        from .models import Profile, Role

        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.force_login(self.user)
        doc, line = self._doc(2)
        hu = self._hu()
        services.pick_from_hu(
            hu=hu, quantity=2, user=self.user, document=doc, line=line
        )
        self.assertEqual(
            IssueDocument.objects.get(pk=doc.pk).status, IssueStatus.OTWARTY
        )
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": hu.number, "quantity": "1", "document": str(doc.pk)},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(resp.json()["document"]["completed"])
        self.assertEqual(
            IssueDocument.objects.get(pk=doc.pk).status, IssueStatus.ZREALIZOWANY
        )


class IssueLineLockTests(BaseSetup):
    """US-052: dodanie i usunięcie pozycji WZ pod blokadą dokumentu."""

    def _doc(self):
        doc = IssueDocument.objects.create(number="WZ-L1", created_by=self.user)
        line = IssueLine.objects.create(
            document=doc, material=self.material, requested_qty=2
        )
        return doc, line

    def test_add_line_rejected_when_closed_meanwhile(self):
        doc, _ = self._doc()
        stale = IssueDocument.objects.get(pk=doc.pk)  # widok wczytał „Otwarty”
        IssueDocument.objects.filter(pk=doc.pk).update(status=IssueStatus.ZREALIZOWANY)
        with self.assertRaisesMessage(WMSError, "tylko w otwartym"):
            services.add_issue_line(
                document=stale, material=self.material, requested_qty=1
            )
        self.assertEqual(doc.lines.count(), 1)

    def test_delete_line_rejected_when_closed_meanwhile(self):
        doc, line = self._doc()
        stale = IssueDocument.objects.get(pk=doc.pk)
        IssueDocument.objects.filter(pk=doc.pk).update(status=IssueStatus.ZREALIZOWANY)
        with self.assertRaisesMessage(WMSError, "tylko w otwartym"):
            services.delete_issue_line(document=stale, line_id=line.pk)
        self.assertTrue(IssueLine.objects.filter(pk=line.pk).exists())

    def test_add_and_delete_on_open_document(self):
        doc, line = self._doc()
        added = services.add_issue_line(
            document=doc, material=self.material, requested_qty=3
        )
        services.delete_issue_line(document=doc, line_id=line.pk)
        self.assertEqual(list(doc.lines.values_list("pk", flat=True)), [added.pk])
        with self.assertRaisesMessage(WMSError, "nie istnieje"):
            services.delete_issue_line(document=doc, line_id=line.pk)

    def test_specific_hu_reservation_checked_in_service(self):
        doc, _ = self._doc()
        hu = HandlingUnit.objects.create(
            number="HU-L1",
            material=self.material,
            quantity=5,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        services.add_issue_line(
            document=doc, material=self.material, requested_qty=4, specific_hu=hu
        )
        with self.assertRaisesMessage(WMSError, "ma tylko 5"):
            services.add_issue_line(
                document=doc, material=self.material, requested_qty=2, specific_hu=hu
            )

    def test_pick_on_deleted_line_is_message_not_500(self):
        """Kryterium 2: pobranie na pozycji usuniętej w międzyczasie → WMSError / 400."""
        from .models import Profile, Role

        doc, line = self._doc()
        hu = HandlingUnit.objects.create(
            number="HU-L2",
            material=self.material,
            quantity=5,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        stale_line = IssueLine.objects.get(pk=line.pk)
        line.delete()
        with self.assertRaisesMessage(WMSError, "usunięta"):
            services.pick_from_hu(
                hu=hu, quantity=1, user=self.user, document=doc, line=stale_line
            )
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.force_login(self.user)
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": hu.number, "quantity": "1", "document": str(doc.pk)},
        )
        self.assertEqual(resp.status_code, 400)
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 5)

    def test_views_use_service_messages(self):
        from .models import Profile, Role

        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.force_login(self.user)
        doc, line = self._doc()
        resp = self.client.post(
            f"/wydania/{doc.pk}/pozycja/",
            {"mode": "material", "material": self.material.pk, "requested_qty": 1},
            follow=True,
        )
        self.assertContains(resp, "Dodano pozycję")
        resp = self.client.post(
            f"/wydania/{doc.pk}/pozycja/{line.pk}/usun/", follow=True
        )
        self.assertContains(resp, "Usunięto pozycję")
        self.assertEqual(doc.lines.count(), 1)

    def test_cannot_delete_partially_picked_line(self):
        """Przegląd [DB] US-052: pobrana część pozycji jest w historii ruchów."""
        doc, line = self._doc()
        hu = HandlingUnit.objects.create(
            number="HU-L3",
            material=self.material,
            quantity=5,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        services.pick_from_hu(
            hu=hu, quantity=1, user=self.user, document=doc, line=line
        )
        with self.assertRaisesMessage(WMSError, "pobrano już 1"):
            services.delete_issue_line(document=doc, line_id=line.pk)
        self.assertTrue(IssueLine.objects.filter(pk=line.pk).exists())

    def test_deleting_last_unpicked_line_closes_document(self):
        doc, line = self._doc()
        hu = HandlingUnit.objects.create(
            number="HU-L4",
            material=self.material,
            quantity=5,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        services.pick_from_hu(
            hu=hu, quantity=2, user=self.user, document=doc, line=line
        )
        extra = services.add_issue_line(
            document=doc, material=self.material, requested_qty=3
        )
        services.delete_issue_line(document=doc, line_id=extra.pk)
        doc.refresh_from_db()
        self.assertEqual(doc.status, IssueStatus.ZREALIZOWANY)

    def test_reservation_counts_only_unpicked_part(self):
        doc, _ = self._doc()
        hu = HandlingUnit.objects.create(
            number="HU-L5",
            material=self.material,
            quantity=10,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        first = services.add_issue_line(
            document=doc, material=self.material, requested_qty=5, specific_hu=hu
        )
        services.pick_from_hu(
            hu=hu, quantity=5, user=self.user, document=doc, line=first
        )
        stale_hu = HandlingUnit.objects.get(pk=hu.pk)
        HandlingUnit.objects.filter(pk=hu.pk).update(
            quantity=4
        )  # ktoś pobrał w międzyczasie
        services.add_issue_line(
            document=doc, material=self.material, requested_qty=4, specific_hu=stale_hu
        )
        with self.assertRaisesMessage(WMSError, "ma tylko 4"):
            services.add_issue_line(
                document=doc,
                material=self.material,
                requested_qty=1,
                specific_hu=stale_hu,
            )


class PalletLockOrderTests(BaseSetup):
    """US-053: realizacja liczy stan palet z wierszy pod blokadą."""

    def test_two_lines_on_same_pallet_partial_sees_first_pick(self):
        hu = HandlingUnit.objects.create(
            number="HU-O1",
            material=self.material,
            quantity=5,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        doc = IssueDocument.objects.create(number="WZ-O1", created_by=self.user)
        for _ in range(2):
            IssueLine.objects.create(
                document=doc, material=self.material, requested_qty=3, specific_hu=hu
            )
        services.execute_issue_document(
            document=doc, user=self.user, allow_partial=True
        )
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 0)
        self.assertEqual(sorted(doc.lines.values_list("picked_qty", flat=True)), [2, 3])

    def test_pick_by_material_partial_takes_what_is_left(self):
        HandlingUnit.objects.create(
            number="HU-O2",
            material=self.material,
            quantity=4,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        used = services.pick_by_material(
            material=self.material, quantity=10, user=self.user, allow_partial=True
        )
        self.assertEqual(sum(take for _, take in used), 4)

    def test_pick_by_material_without_partial_still_refuses_shortage(self):
        HandlingUnit.objects.create(
            number="HU-O3",
            material=self.material,
            quantity=4,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        with self.assertRaisesMessage(WMSError, "Brak wystarczającego stanu"):
            services.pick_by_material(
                material=self.material, quantity=5, user=self.user
            )
