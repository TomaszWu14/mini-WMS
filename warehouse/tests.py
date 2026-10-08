"""Testy kluczowej logiki magazynowej."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from . import services
from .imports import import_locations
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
    Profile,
    Role,
    StockMovement,
    Unit,
)
from .services import WMSError


class BaseSetup(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operator", password="x")
        self.unit = Unit.objects.get_or_create(code="PCS")[0]
        self.material = Material.objects.create(
            index="MAT-1", name="Materiał testowy", unit=self.unit
        )


class SplitQuantityTests(TestCase):
    def test_even_split_remainder_on_last(self):
        self.assertEqual(services.split_quantity(100, 3), [33, 33, 34])

    def test_exact_split(self):
        self.assertEqual(services.split_quantity(90, 3), [30, 30, 30])

    def test_single_pallet(self):
        self.assertEqual(services.split_quantity(7, 1), [7])

    def test_too_many_pallets_raises(self):
        with self.assertRaises(WMSError):
            services.split_quantity(2, 5)


class HUNumberingTests(BaseSetup):
    def test_sequential_unique_numbers(self):
        n1 = services.generate_hu_number()
        n2 = services.generate_hu_number()
        self.assertNotEqual(n1, n2)
        self.assertTrue(n1.startswith("HU"))


class ReceiveTests(BaseSetup):
    def test_receive_creates_hus_and_movements(self):
        quantities = services.split_quantity(100, 3)
        result = services.receive_material(
            material=self.material, quantities=quantities, user=self.user
        )
        self.assertEqual(len(result.handling_units), 3)
        self.assertEqual(sum(hu.quantity for hu in result.handling_units), 100)
        for hu in result.handling_units:
            self.assertEqual(hu.status, HUStatus.DO_ULOZENIA)
            self.assertIsNone(hu.location)
        self.assertEqual(
            StockMovement.objects.filter(type=MovementType.PRZYJECIE).count(), 3
        )

    def test_receive_respects_max_per_pallet(self):
        self.material.max_per_pallet = 30
        self.material.save()
        with self.assertRaises(WMSError):
            services.receive_material(
                material=self.material, quantities=[40], user=self.user
            )


class AllocationTests(BaseSetup):
    def test_allocate_sets_location_and_status(self):
        loc = Location.objects.create(code="A-1", type=LocationType.ZAPAS)
        hu = services.receive_material(
            material=self.material, quantities=[10], user=self.user
        ).handling_units[0]
        services.allocate_hu(hu=hu, location=loc, user=self.user)
        hu.refresh_from_db()
        self.assertEqual(hu.location, loc)
        self.assertEqual(hu.status, HUStatus.ZMAGAZYNOWANY)


class PickingTests(BaseSetup):
    def _make_hu(self, qty, *, loc=None, expiry=None, lot=""):
        hu = HandlingUnit.objects.create(
            number=services.generate_hu_number(),
            material=self.material,
            quantity=qty,
            location=loc,
            expiry_date=expiry,
            lot=lot,
            status=HUStatus.ZMAGAZYNOWANY if loc else HUStatus.DO_ULOZENIA,
        )
        return hu

    def test_fefo_prefers_earliest_expiry(self):
        later = self._make_hu(10, expiry=date.today() + timedelta(days=30))
        sooner = self._make_hu(10, expiry=date.today() + timedelta(days=5))
        used = services.pick_by_material(
            material=self.material, quantity=5, user=self.user
        )
        self.assertEqual(used[0][0].pk, sooner.pk)
        later.refresh_from_db()
        self.assertEqual(later.quantity, 10)

    def test_picking_location_priority(self):
        pick_loc = Location.objects.create(code="P-1", type=LocationType.PICKING)
        zap_loc = Location.objects.create(code="Z-1", type=LocationType.ZAPAS)
        # Zapas ma wcześniejszą datę, ale picking ma priorytet lokalizacji.
        self._make_hu(10, loc=zap_loc, expiry=date.today() + timedelta(days=1))
        picking = self._make_hu(
            10, loc=pick_loc, expiry=date.today() + timedelta(days=99)
        )
        used = services.pick_by_material(
            material=self.material, quantity=5, user=self.user
        )
        self.assertEqual(used[0][0].pk, picking.pk)

    def test_partial_pick_keeps_remainder(self):
        loc = Location.objects.create(code="A-3", type=LocationType.PICKING)
        hu = self._make_hu(10, loc=loc)
        services.pick_from_hu(hu=hu, quantity=4, user=self.user)
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 6)
        self.assertEqual(hu.status, HUStatus.ZMAGAZYNOWANY)
        self.assertEqual(hu.location, loc)

    def test_pick_to_zero_marks_empty_and_frees_location(self):
        loc = Location.objects.create(code="A-2", type=LocationType.ZAPAS)
        hu = self._make_hu(10, loc=loc)
        services.pick_from_hu(hu=hu, quantity=10, user=self.user)
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 0)
        self.assertEqual(hu.status, HUStatus.PUSTY)
        self.assertIsNone(hu.location)

    def test_overpick_blocked(self):
        hu = self._make_hu(5)
        with self.assertRaises(WMSError):
            services.pick_from_hu(hu=hu, quantity=6, user=self.user)

    def test_pick_by_material_insufficient_stock(self):
        self._make_hu(3)
        with self.assertRaises(WMSError):
            services.pick_by_material(
                material=self.material, quantity=10, user=self.user
            )

    def test_pick_spans_multiple_hus(self):
        self._make_hu(4, expiry=date.today() + timedelta(days=1))
        self._make_hu(4, expiry=date.today() + timedelta(days=2))
        used = services.pick_by_material(
            material=self.material, quantity=6, user=self.user
        )
        self.assertEqual(sum(q for _, q in used), 6)


class CorrectionTests(BaseSetup):
    def test_correction_logs_movement(self):
        hu = HandlingUnit.objects.create(
            number=services.generate_hu_number(),
            material=self.material,
            quantity=10,
            status=HUStatus.DO_ULOZENIA,
        )
        services.correct_hu_quantity(hu=hu, new_quantity=7, user=self.user)
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 7)
        move = StockMovement.objects.get(type=MovementType.KOREKTA)
        self.assertEqual(move.quantity_delta, -3)


class IssueDocumentTests(BaseSetup):
    def test_execute_document_picks_lines(self):
        loc = Location.objects.create(code="P-9", type=LocationType.PICKING)
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
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=8)
        services.execute_issue_document(document=doc, user=self.user)
        doc.refresh_from_db()
        self.assertEqual(doc.status, "ZREALIZOWANY")
        line = doc.lines.first()
        self.assertEqual(line.picked_qty, 8)
        self.assertEqual(services.available_quantity(self.material), 12)


class PickingProTests(BaseSetup):
    def _hu(self, qty, number, *, loc=None, expiry=None):
        return HandlingUnit.objects.create(
            number=number,
            material=self.material,
            quantity=qty,
            location=loc,
            expiry_date=expiry,
            status=HUStatus.ZMAGAZYNOWANY if loc else HUStatus.DO_ULOZENIA,
        )

    def test_picking_plan_fefo_and_shortage(self):
        from datetime import date, timedelta

        self._hu(3, "P1", expiry=date.today() + timedelta(days=2))
        self._hu(3, "P2", expiry=date.today() + timedelta(days=10))
        plan = services.picking_plan(self.material, 10)
        self.assertEqual(plan["plan"][0]["hu"], "P1")
        self.assertEqual(plan["plan"][0]["take"], 3)
        self.assertEqual(plan["shortage"], 4)

    def test_partial_execution_closes_with_shortage(self):
        self._hu(4, "PP1")
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=10)
        services.execute_issue_document(
            document=doc, user=self.user, allow_partial=True
        )
        doc.refresh_from_db()
        line = doc.lines.first()
        self.assertEqual(doc.status, "ZREALIZOWANY")
        self.assertEqual(line.picked_qty, 4)
        self.assertEqual(line.shortage, 6)

    def test_full_execution_raises_on_shortage(self):
        self._hu(4, "PP2")
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=10)
        with self.assertRaises(WMSError):
            services.execute_issue_document(document=doc, user=self.user)

    def test_pack_and_ship_flow(self):
        self._hu(10, "PP3")
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=5)
        services.execute_issue_document(document=doc, user=self.user)
        services.pack_issue_document(document=doc, user=self.user)
        doc.refresh_from_db()
        self.assertEqual(doc.status, "SPAKOWANY")
        self.assertIsNotNone(doc.packed_at)
        services.ship_issue_document(
            document=doc, user=self.user, carrier="DPD", tracking="123"
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, "WYSLANY")
        self.assertEqual(doc.carrier, "DPD")
        self.assertEqual(doc.tracking_number, "123")

    def test_pack_requires_realized(self):
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        with self.assertRaises(WMSError):
            services.pack_issue_document(document=doc, user=self.user)

    def test_import_issue_orders(self):
        from .issue_import import import_issue_orders

        data = b"indeks;ilosc;referencja\nMAT-1;5;ZAM-1\nMAT-1;3;ZAM-2\nNIEMA;2;ZAM-2\n"
        result = import_issue_orders("zlec.csv", data, self.user)
        self.assertEqual(result["documents_count"], 2)
        self.assertEqual(result["lines"], 2)
        self.assertEqual(len(result["errors"]), 1)


class ReceiptImportTests(BaseSetup):
    def test_import_receipts_creates_hus(self):
        from .receipt_import import import_receipts

        data = b"indeks;ilosc;palety;dostawa\nMAT-1;100;3;AWIZO-1\n"
        result = import_receipts("przyj.csv", data, self.user)
        self.assertEqual(result["created_hus"], 3)
        self.assertEqual(result["errors"], [])
        self.assertEqual(HandlingUnit.objects.filter(material=self.material).count(), 3)
        self.assertEqual(sum(h.quantity for h in HandlingUnit.objects.all()), 100)

    def test_import_receipts_unknown_material(self):
        from .receipt_import import import_receipts

        data = b"indeks;ilosc\nNIEMA;10\n"
        result = import_receipts("p.csv", data, self.user)
        self.assertEqual(result["created_hus"], 0)
        self.assertEqual(len(result["errors"]), 1)


class ReportViewTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.client.login(username="operator", password="x")
        self.loc = Location.objects.create(code="R1", type=LocationType.ZAPAS)
        HandlingUnit.objects.create(
            number="RH1",
            material=self.material,
            quantity=5,
            location=self.loc,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def test_report_index(self):
        self.assertEqual(self.client.get("/raporty/").status_code, 200)

    def test_report_locations(self):
        resp = self.client.get("/raporty/lokalizacje/")
        self.assertEqual(resp.status_code, 200)

    def test_report_material_history(self):
        resp = self.client.get("/raporty/material/", {"material": "MAT-1"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "MAT-1")


class LocationImportTests(TestCase):
    def test_import_csv(self):
        data = b"kod;typ;pojemnosc\nB0-81-301A;PICKING;1\nB0-81-302A;ZAPAS;2\n"
        created, updated, errors = import_locations("lokalizacje.csv", data)
        self.assertEqual(created, 2)
        self.assertEqual(updated, 0)
        self.assertEqual(errors, [])
        self.assertEqual(
            Location.objects.get(code="B0-81-301A").type, LocationType.PICKING
        )

    def test_import_updates_existing(self):
        Location.objects.create(code="X-1", type=LocationType.ZAPAS, capacity=1)
        data = b"kod,typ,pojemnosc\nX-1,PICKING,5\n"
        created, updated, errors = import_locations("loc.csv", data)
        self.assertEqual((created, updated), (0, 1))
        loc = Location.objects.get(code="X-1")
        self.assertEqual(loc.type, LocationType.PICKING)
        self.assertEqual(loc.capacity, 5)


class StockImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("imp", password="x")
        Unit.objects.get_or_create(code="PCS")

    def test_import_creates_hus_with_own_numbers_and_zero_qty(self):
        from .stock_import import import_stock

        data = (
            "HU;REF;nazwa;lokalizacja;data ważności;partia\n"
            "10476246;XDB-R;Test Dumbbell;Przyjęcia;-;-\n"
            "10476247;XDB-R;Test Dumbbell;Przyjęcia;-;-\n"
        ).encode()
        result = import_stock("stany.csv", data, self.user)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["materials_created"], 1)
        self.assertEqual(result["errors"], [])
        hu = HandlingUnit.objects.get(number="10476246")
        self.assertEqual(hu.quantity, 0)
        self.assertEqual(hu.status, HUStatus.DO_ULOZENIA)
        self.assertIsNone(hu.location)
        self.assertEqual(hu.material.index, "XDB-R")

    def test_import_real_location_allocates(self):
        from .stock_import import import_stock

        data = b"HU,REF,nazwa,ilosc,lokalizacja\n900,MAT-X,Test,5,B0-81-301A\n"
        result = import_stock("stany.csv", data, self.user)
        self.assertEqual(result["created"], 1)
        hu = HandlingUnit.objects.get(number="900")
        self.assertEqual(hu.quantity, 5)
        self.assertEqual(hu.status, HUStatus.ZMAGAZYNOWANY)
        self.assertEqual(hu.location.code, "B0-81-301A")

    def test_import_skips_duplicate_hu(self):
        from .stock_import import import_stock

        data = b"HU,REF,lokalizacja\n111,MAT-A,Przyjecia\n111,MAT-A,Przyjecia\n"
        result = import_stock("stany.csv", data, self.user)
        self.assertEqual(result["created"], 1)
        self.assertEqual(len(result["errors"]), 1)


class ScannerTests(BaseSetup):
    def setUp(self):
        super().setUp()
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        self.loc = Location.objects.create(code="B0-81-301A", type=LocationType.PICKING)
        self.hu = HandlingUnit.objects.create(
            number="HU-SCAN-1",
            material=self.material,
            quantity=10,
            status=HUStatus.DO_ULOZENIA,
        )

    def test_api_hu_lookup(self):
        resp = self.client.get("/skaner/api/hu/", {"code": "HU-SCAN-1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["hu"]["material_index"], "MAT-1")

    def test_api_hu_not_found(self):
        resp = self.client.get("/skaner/api/hu/", {"code": "NIEMA"})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.json()["ok"])

    def test_api_allocate(self):
        resp = self.client.post(
            "/skaner/api/rozmiesc/", {"hu": "HU-SCAN-1", "location": "B0-81-301A"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.location, self.loc)
        self.assertEqual(self.hu.status, HUStatus.ZMAGAZYNOWANY)

    def test_api_pick_partial(self):
        resp = self.client.post(
            "/skaner/api/pick/", {"hu": "HU-SCAN-1", "quantity": "4"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 6)

    def test_api_pick_overpick_blocked(self):
        resp = self.client.post(
            "/skaner/api/pick/", {"hu": "HU-SCAN-1", "quantity": "99"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    def test_scanner_home_requires_operator(self):
        Profile.objects.filter(user=self.user).update(role=Role.VIEWER)
        resp = self.client.get("/skaner/")
        self.assertEqual(resp.status_code, 403)

    def test_api_location_contents(self):
        # HU-SCAN-1 jest w strefie przyjęć; ulokujmy go w self.loc
        services.allocate_hu(hu=self.hu, location=self.loc, user=self.user)
        resp = self.client.get(
            "/skaner/api/lokalizacja-zawartosc/", {"code": "B0-81-301A"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["hus"]), 1)
        self.assertEqual(data["hus"][0]["number"], "HU-SCAN-1")

    def test_api_location_contents_unknown(self):
        resp = self.client.get("/skaner/api/lokalizacja-zawartosc/", {"code": "NIEMA"})
        self.assertEqual(resp.status_code, 404)

    def test_scanner_info_and_locinfo_render(self):
        self.assertEqual(self.client.get("/skaner/podglad/").status_code, 200)
        self.assertEqual(self.client.get("/skaner/lokalizacja/").status_code, 200)

    def test_api_inventory_add_and_subtract(self):
        resp = self.client.post(
            "/skaner/api/inwentaryzacja/", {"hu": "HU-SCAN-1", "delta": "5"}
        )
        self.assertEqual(resp.status_code, 200)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 15)
        resp = self.client.post(
            "/skaner/api/inwentaryzacja/", {"hu": "HU-SCAN-1", "delta": "-3"}
        )
        self.assertEqual(resp.status_code, 200)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 12)

    def test_api_inventory_cannot_go_negative(self):
        resp = self.client.post(
            "/skaner/api/inwentaryzacja/", {"hu": "HU-SCAN-1", "delta": "-99"}
        )
        self.assertEqual(resp.status_code, 400)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 10)

    def test_document_pick_completes_order(self):
        services.allocate_hu(hu=self.hu, location=self.loc, user=self.user)
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=6)
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": "HU-SCAN-1", "quantity": "6", "document": str(doc.pk)},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["document"]["completed"])
        doc.refresh_from_db()
        self.assertEqual(doc.status, "ZREALIZOWANY")

    def test_document_pick_rejects_wrong_material(self):
        other = Material.objects.create(index="MAT-2", name="Inny", unit=self.unit)
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        IssueLine.objects.create(document=doc, material=other, requested_qty=3)
        resp = self.client.post(
            "/skaner/api/pick/",
            {"hu": "HU-SCAN-1", "quantity": "1", "document": str(doc.pk)},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])


class RepackTests(BaseSetup):
    def _hu(self, qty, number):
        return HandlingUnit.objects.create(
            number=number,
            material=self.material,
            quantity=qty,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def test_repack_same_material(self):
        src = self._hu(10, "SRC-1")
        tgt = self._hu(5, "TGT-1")
        services.repack_hu(source=src, target=tgt, quantity=4, user=self.user)
        src.refresh_from_db()
        tgt.refresh_from_db()
        self.assertEqual(src.quantity, 6)
        self.assertEqual(tgt.quantity, 9)
        self.assertEqual(
            StockMovement.objects.filter(type=MovementType.PRZEPAKOWANIE).count(), 2
        )

    def test_repack_emptied_source_becomes_empty(self):
        src = self._hu(4, "SRC-2")
        tgt = self._hu(1, "TGT-2")
        services.repack_hu(source=src, target=tgt, quantity=4, user=self.user)
        src.refresh_from_db()
        self.assertEqual(src.quantity, 0)
        self.assertEqual(src.status, HUStatus.PUSTY)
        self.assertIsNone(src.location)

    def test_repack_different_material_blocked(self):
        other_mat = Material.objects.create(index="MAT-9", name="Inny", unit=self.unit)
        src = self._hu(10, "SRC-3")
        tgt = HandlingUnit.objects.create(
            number="TGT-3",
            material=other_mat,
            quantity=2,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        with self.assertRaises(WMSError):
            services.repack_hu(source=src, target=tgt, quantity=1, user=self.user)

    def test_repack_over_source_blocked(self):
        src = self._hu(3, "SRC-4")
        tgt = self._hu(0 + 1, "TGT-4")
        with self.assertRaises(WMSError):
            services.repack_hu(source=src, target=tgt, quantity=5, user=self.user)


class WebInventoryTests(BaseSetup):
    def setUp(self):
        super().setUp()
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        self.hu = HandlingUnit.objects.create(
            number="INV-1",
            material=self.material,
            quantity=10,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def test_web_inventory_add(self):
        resp = self.client.post(
            "/inwentaryzacja/",
            {"hu_number": "INV-1", "mode": "add", "quantity": "5"},
        )
        self.assertEqual(resp.status_code, 302)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 15)

    def test_web_inventory_subtract(self):
        resp = self.client.post(
            "/inwentaryzacja/",
            {"hu_number": "INV-1", "mode": "sub", "quantity": "4"},
        )
        self.assertEqual(resp.status_code, 302)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 6)

    def test_web_inventory_negative_blocked(self):
        resp = self.client.post(
            "/inwentaryzacja/",
            {"hu_number": "INV-1", "mode": "sub", "quantity": "99"},
        )
        self.assertEqual(resp.status_code, 200)  # formularz z błędem
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 10)

    def test_web_inventory_requires_operator(self):
        Profile.objects.filter(user=self.user).update(role=Role.VIEWER)
        resp = self.client.get("/inwentaryzacja/")
        self.assertEqual(resp.status_code, 403)


class StocktakeTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.loc = Location.objects.create(code="L1", type=LocationType.ZAPAS)
        self.hu = HandlingUnit.objects.create(
            number="ST-1",
            material=self.material,
            quantity=10,
            location=self.loc,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def test_create_stocktake_snapshots_stock(self):
        sheet = services.create_stocktake(location=self.loc, user=self.user)
        self.assertEqual(sheet.lines.count(), 1)
        line = sheet.lines.first()
        self.assertEqual(line.expected_qty, 10)
        self.assertEqual(line.location_code, "L1")

    def test_close_applies_variance_with_reason(self):
        from .models import AdjustReason

        sheet = services.create_stocktake(location=self.loc, user=self.user)
        line = sheet.lines.first()
        line.counted_qty = 7
        line.save()
        result = services.close_stocktake(sheet=sheet, user=self.user)
        self.assertEqual(result["adjusted"], 1)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 7)
        move = StockMovement.objects.filter(
            type=MovementType.KOREKTA, reason=AdjustReason.SPIS
        ).first()
        self.assertIsNotNone(move)
        self.assertEqual(move.quantity_delta, -3)

    def test_close_without_count_no_change(self):
        sheet = services.create_stocktake(location=self.loc, user=self.user)
        result = services.close_stocktake(sheet=sheet, user=self.user)
        self.assertEqual(result["adjusted"], 0)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 10)


class WebRepackTests(BaseSetup):
    def setUp(self):
        super().setUp()
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        self.src = HandlingUnit.objects.create(
            number="WR-S",
            material=self.material,
            quantity=10,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        self.tgt = HandlingUnit.objects.create(
            number="WR-T",
            material=self.material,
            quantity=2,
            status=HUStatus.ZMAGAZYNOWANY,
        )

    def test_web_repack_same_material(self):
        resp = self.client.post(
            "/przepakowanie/",
            {"source_number": "WR-S", "target_number": "WR-T", "quantity": "4"},
        )
        self.assertEqual(resp.status_code, 302)
        self.src.refresh_from_db()
        self.tgt.refresh_from_db()
        self.assertEqual(self.src.quantity, 6)
        self.assertEqual(self.tgt.quantity, 6)

    def test_web_repack_different_material_blocked(self):
        other = Material.objects.create(index="M-OTH", name="X", unit=self.unit)
        HandlingUnit.objects.create(
            number="WR-O",
            material=other,
            quantity=3,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        resp = self.client.post(
            "/przepakowanie/",
            {"source_number": "WR-S", "target_number": "WR-O", "quantity": "1"},
        )
        self.assertEqual(resp.status_code, 200)
        self.src.refresh_from_db()
        self.assertEqual(self.src.quantity, 10)


class PdfAndViewTests(BaseSetup):
    def setUp(self):
        super().setUp()
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        self.loc = Location.objects.create(code="P1", type=LocationType.PICKING)

    def test_location_label_pdf(self):
        resp = self.client.get(f"/lokalizacje/{self.loc.pk}/etykieta/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF-"))

    def test_issue_pdf(self):
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        IssueLine.objects.create(document=doc, material=self.material, requested_qty=3)
        resp = self.client.get(f"/wydania/{doc.pk}/pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF-"))

    def test_stock_by_location_page(self):
        resp = self.client.get("/stany/lokalizacje/")
        self.assertEqual(resp.status_code, 200)

    def test_hu_label_with_all_fields_single_page(self):
        """Etykieta z kompletem opcjonalnych pól nie wychodzi poza stronę A4."""
        from .labels import hu_labels_pdf

        hu = HandlingUnit.objects.create(
            number="HU-FULL-1",
            material=self.material,
            quantity=120,
            location=self.loc,
            status=HUStatus.ZMAGAZYNOWANY,
            lot="LOT-2026-001",
            delivery_ref="AWIZO-2026-0001",
            delivery_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
        )
        pdf = hu_labels_pdf([hu])
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 1000)

    def test_delivery_edit_admin_only(self):
        hu = HandlingUnit.objects.create(
            number="DD-1",
            material=self.material,
            quantity=5,
            status=HUStatus.DO_ULOZENIA,
        )
        # operator (rola OPERATOR z setUp) nie ma dostępu
        resp = self.client.get(f"/hu/{hu.pk}/dostawa/")
        self.assertEqual(resp.status_code, 403)
        # admin może zmienić termin dostawy
        Profile.objects.filter(user=self.user).update(role=Role.ADMIN)
        resp = self.client.post(
            f"/hu/{hu.pk}/dostawa/",
            {"delivery_date": "2026-07-15", "delivery_ref": "DOSTAWA-9"},
        )
        self.assertEqual(resp.status_code, 302)
        hu.refresh_from_db()
        self.assertEqual(str(hu.delivery_date), "2026-07-15")
        self.assertEqual(hu.delivery_ref, "DOSTAWA-9")


class UserManagementTests(BaseSetup):
    def setUp(self):
        super().setUp()
        Profile.objects.filter(user=self.user).update(role=Role.ADMIN)
        self.client.login(username="operator", password="x")

    def test_user_list_admin_only(self):
        resp = self.client.get("/uzytkownicy/")
        self.assertEqual(resp.status_code, 200)
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        resp = self.client.get("/uzytkownicy/")
        self.assertEqual(resp.status_code, 403)

    def test_create_user_with_role(self):
        resp = self.client.post(
            "/uzytkownicy/nowy/",
            {
                "username": "magazyn1",
                "email": "m@example.com",
                "password": "tajnehaslo",
                "role": Role.OPERATOR,
            },
        )
        self.assertEqual(resp.status_code, 302)
        u = User.objects.get(username="magazyn1")
        self.assertEqual(u.profile.role, Role.OPERATOR)
        self.assertTrue(u.check_password("tajnehaslo"))

    def test_edit_user_role_and_password(self):
        target = User.objects.create_user("op2", password="old")
        resp = self.client.post(
            f"/uzytkownicy/{target.pk}/",
            {"role": Role.VIEWER, "is_active": "on", "new_password": "noweHaslo123"},
        )
        self.assertEqual(resp.status_code, 302)
        target.refresh_from_db()
        self.assertEqual(target.profile.role, Role.VIEWER)
        self.assertTrue(target.check_password("noweHaslo123"))

    def test_cannot_deactivate_self(self):
        self.client.post(
            f"/uzytkownicy/{self.user.pk}/",
            {"role": Role.ADMIN, "is_active": ""},
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)


class RoleTests(TestCase):
    def test_superuser_profile_is_admin(self):
        su = User.objects.create_superuser("admin", password="x")
        self.assertEqual(su.profile.role, Role.ADMIN)

    def test_new_user_default_viewer(self):
        u = User.objects.create_user("viewer", password="x")
        self.assertEqual(u.profile.role, Role.VIEWER)


class ViewAccessTests(BaseSetup):
    def test_login_required_redirects(self):
        resp = self.client.get("/przyjecie/")
        self.assertEqual(resp.status_code, 302)

    def test_viewer_cannot_receive(self):
        self.client.login(username="operator", password="x")
        # operator domyślnie ma profil VIEWER, podnieśmy do OPERATOR
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        resp = self.client.get("/przyjecie/")
        self.assertEqual(resp.status_code, 200)

    def test_viewer_role_forbidden_on_receive(self):
        Profile.objects.filter(user=self.user).update(role=Role.VIEWER)
        self.client.login(username="operator", password="x")
        resp = self.client.get("/przyjecie/")
        self.assertEqual(resp.status_code, 403)

    def test_dashboard_ok(self):
        self.client.login(username="operator", password="x")
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)


class SecurityTests(BaseSetup):
    """Dziennik logowań, silne hasła i ochrona własnej roli administratora."""

    def setUp(self):
        super().setUp()
        self.user.set_password("Sekret123!")
        self.user.save()
        Profile.objects.filter(user=self.user).update(role=Role.ADMIN)

    def test_successful_login_is_logged(self):
        from .models import LoginEvent

        self.assertTrue(self.client.login(username="operator", password="Sekret123!"))
        event = LoginEvent.objects.filter(kind=LoginEvent.Kind.LOGIN).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.username, "operator")
        self.assertEqual(event.user, self.user)

    def test_failed_login_is_logged(self):
        from .models import LoginEvent

        self.client.login(username="operator", password="zle-haslo")
        event = LoginEvent.objects.filter(kind=LoginEvent.Kind.FAILED).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.username, "operator")
        self.assertIsNone(event.user)

    def test_logout_is_logged(self):
        from .models import LoginEvent

        self.client.login(username="operator", password="Sekret123!")
        self.client.logout()
        self.assertTrue(LoginEvent.objects.filter(kind=LoginEvent.Kind.LOGOUT).exists())

    def test_login_log_view_admin_only(self):
        self.client.login(username="operator", password="Sekret123!")
        resp = self.client.get("/uzytkownicy/dziennik/")
        self.assertEqual(resp.status_code, 200)
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        resp = self.client.get("/uzytkownicy/dziennik/")
        self.assertEqual(resp.status_code, 403)

    def test_weak_password_rejected_on_create(self):
        self.client.login(username="operator", password="Sekret123!")
        resp = self.client.post(
            "/uzytkownicy/nowy/",
            {
                "username": "slaby",
                "email": "",
                "password": "123",
                "role": Role.OPERATOR,
            },
        )
        self.assertEqual(resp.status_code, 200)  # formularz z błędem
        self.assertFalse(User.objects.filter(username="slaby").exists())

    def test_strong_password_accepted_on_create(self):
        self.client.login(username="operator", password="Sekret123!")
        resp = self.client.post(
            "/uzytkownicy/nowy/",
            {
                "username": "mocny",
                "email": "",
                "password": "BardzoTajne123",
                "role": Role.OPERATOR,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(username="mocny").exists())

    def test_invalid_username_rejected(self):
        self.client.login(username="operator", password="Sekret123!")
        resp = self.client.post(
            "/uzytkownicy/nowy/",
            {
                "username": "zly login!",
                "email": "",
                "password": "BardzoTajne123",
                "role": Role.OPERATOR,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="zly login!").exists())

    def test_admin_cannot_demote_own_role(self):
        self.client.login(username="operator", password="Sekret123!")
        self.client.post(
            f"/uzytkownicy/{self.user.pk}/",
            {"role": Role.OPERATOR, "is_active": "on"},
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.role, Role.ADMIN)

    def test_password_similar_to_username_rejected(self):
        """validate_password z userem odrzuca hasło zbyt podobne do loginu."""
        self.client.login(username="operator", password="Sekret123!")
        resp = self.client.post(
            "/uzytkownicy/nowy/",
            {
                "username": "jankowalski",
                "email": "",
                "password": "jankowalski",
                "role": Role.OPERATOR,
            },
        )
        self.assertEqual(resp.status_code, 200)  # formularz z błędem
        self.assertFalse(User.objects.filter(username="jankowalski").exists())

    def test_failed_login_with_none_username_does_not_crash(self):
        """Sygnał nieudanego logowania nie wywraca się, gdy username=None."""
        from django.contrib.auth.signals import user_login_failed

        from .models import LoginEvent

        # Backend może wysłać credentials z username=None — nie może rzucić.
        user_login_failed.send(
            sender=self.__class__,
            credentials={"username": None, "password": "x"},
            request=None,
        )
        self.assertTrue(LoginEvent.objects.filter(kind=LoginEvent.Kind.FAILED).exists())

    def test_login_log_pagination(self):
        """Dziennik stronicuje i nie gubi zdarzeń powyżej rozmiaru strony."""
        from .models import LoginEvent

        LoginEvent.objects.bulk_create(
            [
                LoginEvent(username=f"u{i}", kind=LoginEvent.Kind.LOGIN)
                for i in range(150)
            ]
        )
        self.client.login(username="operator", password="Sekret123!")
        resp = self.client.get("/uzytkownicy/dziennik/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["page_obj"].paginator.num_pages, 2)
        resp2 = self.client.get("/uzytkownicy/dziennik/?page=2")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.context["page_obj"].number, 2)


class HardeningTests(BaseSetup):
    """Testy poprawek z audytu: injection, walidacja, numeracja, role."""

    def test_csv_export_neutralizes_formula_injection(self):
        from .exports import _safe_cell

        self.assertEqual(_safe_cell("=1+1"), "'=1+1")
        self.assertEqual(_safe_cell("+SUM(A1)"), "'+SUM(A1)")
        self.assertEqual(_safe_cell("-2"), "'-2")
        self.assertEqual(_safe_cell("@cmd"), "'@cmd")
        self.assertEqual(_safe_cell("MAT-1"), "MAT-1")  # zwykły tekst bez zmian
        self.assertEqual(_safe_cell(120), 120)  # liczby nietknięte

    def test_export_rejects_unknown_format(self):
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        self.assertEqual(self.client.get("/stany/eksport/json/").status_code, 404)
        self.assertEqual(self.client.get("/ruchy/eksport/pdf/").status_code, 404)
        self.assertEqual(self.client.get("/stany/eksport/csv/").status_code, 200)

    def test_shortage_zero_while_open_and_real_after_realization(self):
        loc = Location.objects.create(code="SH1", type=LocationType.PICKING)
        HandlingUnit.objects.create(
            number="SHH",
            material=self.material,
            quantity=4,
            location=loc,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        line = IssueLine.objects.create(
            document=doc, material=self.material, requested_qty=10
        )
        # Dokument otwarty — brak to jeszcze „do pobrania", nie niedobór.
        self.assertEqual(line.shortage, 0)
        self.assertEqual(line.outstanding, 10)
        services.execute_issue_document(
            document=doc, user=self.user, allow_partial=True
        )
        line.refresh_from_db()
        self.assertEqual(line.shortage, 6)  # po realizacji 4/10 → brak 6

    def test_superuser_promotion_syncs_admin_role(self):
        u = User.objects.create_user("zwykly", password="x")
        self.assertEqual(u.profile.role, Role.VIEWER)
        u.is_superuser = True
        u.save()
        u.refresh_from_db()
        self.assertEqual(u.profile.role, Role.ADMIN)

    def test_save_with_unique_number_retries_on_collision(self):
        # Symulujemy generator, który najpierw zwraca zajęty numer, potem nowy.
        existing = IssueDocument.objects.create(number="WZDUP-1", created_by=self.user)
        numbers = iter(["WZDUP-1", "WZDUP-2"])
        doc = services.save_with_unique_number(
            IssueDocument(created_by=self.user), lambda: next(numbers)
        )
        self.assertEqual(doc.number, "WZDUP-2")
        self.assertNotEqual(doc.pk, existing.pk)

    def test_available_quantity_sums_active_hus(self):
        HandlingUnit.objects.create(
            number="AQ1",
            material=self.material,
            quantity=7,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        HandlingUnit.objects.create(
            number="AQ2",
            material=self.material,
            quantity=3,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        HandlingUnit.objects.create(
            number="AQ3",
            material=self.material,
            quantity=0,
            status=HUStatus.PUSTY,
        )
        self.assertEqual(services.available_quantity(self.material), 10)


class AuditFixTests(BaseSetup):
    """Druga fala poprawek z audytu (40 bugów)."""

    def test_allocate_enforces_capacity(self):
        loc = Location.objects.create(code="CAP1", type=LocationType.ZAPAS, capacity=1)
        hu1 = HandlingUnit.objects.create(
            number="C1",
            material=self.material,
            quantity=5,
            status=HUStatus.DO_ULOZENIA,
        )
        hu2 = HandlingUnit.objects.create(
            number="C2",
            material=self.material,
            quantity=5,
            status=HUStatus.DO_ULOZENIA,
        )
        services.allocate_hu(hu=hu1, location=loc, user=self.user)
        with self.assertRaises(services.WMSError):
            services.allocate_hu(hu=hu2, location=loc, user=self.user)

    def test_daily_number_is_deletion_safe(self):
        from .services import _next_daily_number

        IssueDocument.objects.create(number="WZX-001", created_by=self.user)
        IssueDocument.objects.create(number="WZX-002", created_by=self.user)
        IssueDocument.objects.filter(number="WZX-001").delete()
        # Mimo usunięcia -001 kolejny numer to -003 (max+1), nie istniejący -002.
        self.assertEqual(_next_daily_number(IssueDocument, "WZX"), "WZX-003")

    def test_execute_rejects_specific_hu_wrong_material(self):
        other = Material.objects.create(index="OTH", name="x", unit=self.unit)
        loc = Location.objects.create(code="L9", type=LocationType.PICKING)
        hu = HandlingUnit.objects.create(
            number="SP1",
            material=other,
            quantity=10,
            location=loc,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        IssueLine.objects.create(
            document=doc, material=self.material, requested_qty=3, specific_hu=hu
        )
        with self.assertRaises(services.WMSError):
            services.execute_issue_document(document=doc, user=self.user)

    def test_correct_reactivates_emptied_hu(self):
        hu = HandlingUnit.objects.create(
            number="RE1",
            material=self.material,
            quantity=0,
            status=HUStatus.PUSTY,
        )
        services.correct_hu_quantity(hu=hu, new_quantity=5, user=self.user)
        hu.refresh_from_db()
        self.assertEqual(hu.quantity, 5)
        self.assertEqual(hu.status, HUStatus.DO_ULOZENIA)

    def test_cannot_add_line_to_packed_document(self):
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(),
            created_by=self.user,
            status=IssueStatus.SPAKOWANY,
        )
        resp = self.client.post(
            f"/wydania/{doc.pk}/pozycja/",
            {"mode": "material", "material": self.material.pk, "requested_qty": "2"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(doc.lines.count(), 0)

    def test_parse_int_cell(self):
        from .imports import parse_int_cell

        self.assertEqual(parse_int_cell("5,0"), 5)
        self.assertEqual(parse_int_cell("1 234"), 1234)
        self.assertIsNone(parse_int_cell("-"))
        self.assertIsNone(parse_int_cell(""))
        self.assertEqual(parse_int_cell(7), 7)
        with self.assertRaises(ValueError):
            parse_int_cell("abc")

    def test_csv_decode_cp1250_fallback(self):
        from .imports import _decode_csv

        text = "kod;nazwa\nB0-1;Pałka".encode("cp1250")
        self.assertIn("Pałka", _decode_csv(text))

    def test_receipt_import_case_insensitive_material(self):
        from .receipt_import import import_receipts

        data = b"indeks;ilosc;palety\nmat-1;10;1\n"  # plik ma mały rejestr
        result = import_receipts("p.csv", data, self.user)
        self.assertEqual(result["created_hus"], 1)
        self.assertEqual(result["errors"], [])

    def test_hu_quantity_check_constraint(self):
        from django.db import IntegrityError, transaction

        hu = HandlingUnit.objects.create(
            number="CK1",
            material=self.material,
            quantity=5,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HandlingUnit.objects.filter(pk=hu.pk).update(quantity=-1)

    def test_stocktake_line_unique_per_hu(self):
        from django.db import IntegrityError, transaction

        from .models import StocktakeLine

        loc = Location.objects.create(code="STK", type=LocationType.ZAPAS)
        hu = HandlingUnit.objects.create(
            number="STKH",
            material=self.material,
            quantity=5,
            location=loc,
            status=HUStatus.ZMAGAZYNOWANY,
        )
        sheet = services.create_stocktake(location=loc, user=self.user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StocktakeLine.objects.create(
                    sheet=sheet,
                    handling_unit=hu,
                    material=self.material,
                    expected_qty=5,
                )

    def test_wz_pdf_multipage_redraws_header(self):
        """Wielostronicowy WZ (dużo pozycji) nie wywraca się i ma > 1 strony."""
        from .documents import issue_document_pdf

        doc = IssueDocument.objects.create(
            number=services.generate_issue_number(), created_by=self.user
        )
        for n in range(60):
            m = Material.objects.create(
                index=f"WZM-{n:03d}", name=f"Mat {n}", unit=self.unit
            )
            IssueLine.objects.create(document=doc, material=m, requested_qty=1)
        pdf = issue_document_pdf(doc)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreaterEqual(pdf.count(b"/Type /Page"), 2)

    def test_api_document_rejects_non_numeric_id(self):
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        resp = self.client.get("/skaner/api/zlecenie/", {"id": "abc"})
        self.assertEqual(resp.status_code, 404)  # 404, nie 500

    def test_movement_export_respects_type_filter(self):
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        hu = HandlingUnit.objects.create(
            number="MEX",
            material=self.material,
            quantity=5,
            status=HUStatus.DO_ULOZENIA,
        )
        loc = Location.objects.create(code="MEXL", type=LocationType.ZAPAS)
        services.allocate_hu(hu=hu, location=loc, user=self.user)  # ALOKACJA
        # filtr PRZYJECIE nie powinien zawierać ruchu ALOKACJA
        resp = self.client.get("/ruchy/eksport/csv/", {"type": "ALOKACJA"})
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("Alokacja", body)
        self.assertNotIn("Przyjęcie", body)

    def test_healthz_public_and_ok(self):
        """Healthcheck kontenera — bez logowania, 200 i status bazy."""
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["db"])


class ViewLayerTests(BaseSetup):
    """Testy HTTP warstwy widoków dla przepływów wcześniej bez pokrycia."""

    def setUp(self):
        super().setUp()
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")

    def test_receive_view_creates_hus(self):
        resp = self.client.post(
            "/przyjecie/",
            {
                "material": self.material.pk,
                "mode": "total",
                "total_quantity": "100",
                "pallets": "4",
            },
        )
        self.assertEqual(resp.status_code, 302)
        hus = HandlingUnit.objects.filter(material=self.material)
        self.assertEqual(hus.count(), 4)
        self.assertEqual(sum(h.quantity for h in hus), 100)

    def test_hu_allocate_view(self):
        hu = HandlingUnit.objects.create(
            number="ALV-1",
            material=self.material,
            quantity=5,
            status=HUStatus.DO_ULOZENIA,
        )
        loc = Location.objects.create(code="ALV-L", type=LocationType.ZAPAS)
        resp = self.client.post(f"/hu/{hu.pk}/alokacja/", {"location": loc.pk})
        self.assertEqual(resp.status_code, 302)
        hu.refresh_from_db()
        self.assertEqual(hu.location, loc)
        self.assertEqual(hu.status, HUStatus.ZMAGAZYNOWANY)

    def test_movement_list_renders_and_filters(self):
        HandlingUnit.objects.create(
            number="MLV",
            material=self.material,
            quantity=5,
            status=HUStatus.DO_ULOZENIA,
        )
        StockMovement.objects.create(
            type=MovementType.PRZYJECIE,
            material=self.material,
            quantity_delta=5,
            created_by=self.user,
        )
        self.assertEqual(self.client.get("/ruchy/").status_code, 200)
        resp = self.client.get("/ruchy/", {"type": "PRZYJECIE"})
        self.assertEqual(resp.status_code, 200)

    def test_issue_import_view(self):
        data = b"indeks;ilosc;referencja\nMAT-1;5;ZAM-1\n"
        upload = SimpleUploadedFile("zlec.csv", data, content_type="text/csv")
        resp = self.client.post("/wydania/import/", {"file": upload})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(IssueDocument.objects.count(), 1)
        self.assertEqual(IssueLine.objects.count(), 1)
