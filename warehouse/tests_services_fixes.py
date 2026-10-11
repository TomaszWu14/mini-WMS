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
