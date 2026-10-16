"""US-013: walidacja zakresów, długości i nagłówków z danych użytkownika.

Kryterium 2 wymaga PostgreSQL (SQLite nie pilnuje zakresu INTEGER ani długości VARCHAR):
CI uruchamia ten plik także w jobie „3b. Testy (PostgreSQL 16)”.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from . import services
from .imports import import_locations, parse_int_cell
from .issue_import import import_issue_orders
from .models import (
    HandlingUnit,
    HUStatus,
    IssueDocument,
    Location,
    Material,
    Profile,
    Role,
    StockMovement,
    StocktakeLine,
    StocktakeSheet,
    Unit,
)
from .receipt_import import import_receipts
from .stock_import import import_stock

TOO_BIG = 2**31  # poza INTEGER w PostgreSQL


def _csv(header, *rows):
    lines = [";".join(header)] + [";".join(map(str, r)) for r in rows]
    return ("\n".join(lines) + "\n").encode()


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("op", password="OpPass123!")
        Profile.objects.filter(user=self.user).update(role=Role.ADMIN)
        self.client.force_login(self.user)
        self.unit = Unit.objects.get_or_create(code="PCS")[0]
        self.material = Material.objects.create(
            index="MAT-V", name="Walidacja", unit=self.unit
        )
        self.loc = Location.objects.create(code="A-01")
        self.hu = HandlingUnit.objects.create(
            number="HU-V-1",
            material=self.material,
            quantity=10,
            status=HUStatus.ZMAGAZYNOWANY,
            location=self.loc,
        )


class ImportNumberTests(_Base):
    """Kryterium 1: liczby w zapisie wykładniczym poza zakresem."""

    def test_parse_int_cell_rejects_overflow_and_inf(self):
        for value in ("1e999", "1e20", "-1e20", "nan", "inf", str(TOO_BIG)):
            with (
                self.subTest(value=value),
                self.assertRaisesMessage(ValueError, "nieprawidłowa liczba"),
            ):
                parse_int_cell(value)
        self.assertEqual(parse_int_cell("1e3"), 1000)
        self.assertEqual(parse_int_cell("5,0"), 5)

    def test_all_imports_skip_row_with_message(self):
        cases = (
            (
                import_receipts,
                _csv(["indeks", "ilosc"], ("MAT-V", "1e999"), ("MAT-V", "5")),
                "created_hus",
            ),
            (
                import_stock,
                _csv(["REF", "ilosc"], ("MAT-V", "1e999"), ("MAT-V", "5")),
                "created",
            ),
            (
                import_issue_orders,
                _csv(["indeks", "ilosc"], ("MAT-V", "1e20"), ("MAT-V", "5")),
                "lines",
            ),
        )
        for func, data, key in cases:
            with self.subTest(func=func.__name__):
                result = func("x.csv", data, self.user)
                self.assertEqual(result[key], 1)
                self.assertTrue(
                    any(
                        "Wiersz 2" in e and "nieprawidłowa liczba" in e
                        for e in result["errors"]
                    ),
                    result["errors"],
                )

    def test_location_capacity_overflow(self):
        created, _, errors = import_locations(
            "l.csv", _csv(["kod", "pojemnosc"], ("B-01", "1e999"), ("B-02", "3"))
        )
        self.assertEqual(created, 1)
        self.assertIn("nieprawidłowa liczba", errors[0])


class FormRangeTests(_Base):
    """Kryterium 2: pola całkowite > 2^31−1 → błąd pola, nie DataError."""

    def test_forms_reject_huge_numbers(self):
        cases = (
            (
                f"/hu/{self.hu.pk}/korekta/",
                {"new_quantity": TOO_BIG, "reason": "INNE"},
                "new_quantity",
            ),
            (
                "/przepakowanie/",
                {
                    "source_number": "HU-V-1",
                    "target_number": "HU-V-1",
                    "quantity": TOO_BIG,
                },
                "quantity",
            ),
            (
                "/lokalizacje/nowa/",
                {"code": "Z-99", "type": "ZAPAS", "capacity": TOO_BIG},
                "capacity",
            ),
            (
                "/materialy/nowy/",
                {
                    "index": "M-BIG",
                    "name": "x",
                    "unit": self.unit.pk,
                    "max_per_pallet": TOO_BIG,
                },
                "max_per_pallet",
            ),
        )
        for url, data, field in cases:
            with self.subTest(url=url):
                resp = self.client.post(url, data)
                self.assertEqual(resp.status_code, 200, url)
                self.assertIn(field, resp.context["form"].errors)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 10)

    def test_issue_line_huge_quantity(self):
        doc = IssueDocument.objects.create(number="WZ-V-1", created_by=self.user)
        resp = self.client.post(
            f"/wydania/{doc.pk}/pozycja/",
            {
                "mode": "material",
                "material": self.material.pk,
                "requested_qty": TOO_BIG,
            },
        )
        self.assertLess(resp.status_code, 500)
        self.assertFalse(doc.lines.exists())

    def test_inventory_web_form_huge_quantity(self):
        resp = self.client.post(
            "/inwentaryzacja/",
            {
                "hu_number": "HU-V-1",
                "mode": "add",
                "quantity": TOO_BIG,
                "reason": "INNE",
            },
        )
        self.assertLess(resp.status_code, 500)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 10)


class QuantityLimitTests(_Base):
    """Kryterium 3: spis i API skanera z wartością > L_QTY."""

    def test_stocktake_save_skips_value_over_limit(self):
        sheet = StocktakeSheet.objects.create(number="SP-V-1", created_by=self.user)
        line = StocktakeLine.objects.create(
            sheet=sheet,
            handling_unit=self.hu,
            material=self.material,
            location_code="A-01",
            expected_qty=10,
        )
        resp = self.client.post(
            f"/spis/{sheet.pk}/zapisz/",
            {f"counted_{line.id}": services.MAX_QUANTITY + 1},
            follow=True,
        )
        self.assertContains(resp, "Pominięto 1")
        line.refresh_from_db()
        self.assertIsNone(line.counted_qty)

    def test_scanner_api_rejects_out_of_range(self):
        moves = StockMovement.objects.count()
        for value in (
            str(services.MAX_QUANTITY + 1),
            str(-(services.MAX_QUANTITY + 1)),
            "1e9",
            "9" * 30,
        ):
            with self.subTest(value=value):
                resp = self.client.post(
                    "/skaner/api/inwentaryzacja/",
                    {"hu": "HU-V-1", "delta": value, "reason": "INNE"},
                )
                self.assertEqual(resp.status_code, 400)
                self.assertFalse(resp.json()["ok"])
        resp = self.client.post(
            "/skaner/api/przepakuj/",
            {"source": "HU-V-1", "target": "HU-V-1", "quantity": str(TOO_BIG)},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(StockMovement.objects.count(), moves)

    def test_scanner_api_accepts_valid_delta(self):
        resp = self.client.post(
            "/skaner/api/inwentaryzacja/",
            {"hu": "HU-V-1", "delta": "-3", "reason": "INNE"},
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.hu.refresh_from_db()
        self.assertEqual(self.hu.quantity, 7)


class ImportLengthTests(_Base):
    """Kryterium 4: kod lokalizacji > 40 lub numer HU > 30 → wiersz pominięty, nic nie powstaje."""

    def test_stock_import_long_codes_skip_row_without_side_effects(self):
        data = _csv(
            ["REF", "lokalizacja", "hu", "ilosc"],
            ("NOWY-1", "L" * 41, "", 1),
            ("NOWY-2", "B-01", "H" * 31, 1),
            ("NOWY-3", "B-02", "", 1),
        )
        result = import_stock("s.csv", data, self.user)
        self.assertEqual(result["created"], 1)
        self.assertTrue(
            any("Wiersz 2" in e and "kod lokalizacji" in e for e in result["errors"])
        )
        self.assertTrue(
            any("Wiersz 3" in e and "numer HU" in e for e in result["errors"])
        )
        # Bez częściowego zapisu: materiały i lokalizacje z odrzuconych wierszy nie powstały.
        self.assertFalse(
            Material.objects.filter(index__in=["NOWY-1", "NOWY-2"]).exists()
        )
        self.assertFalse(Location.objects.filter(code="B-01").exists())

    def test_location_import_long_code(self):
        created, _, errors = import_locations(
            "l.csv", _csv(["kod"], ("L" * 41,), ("C-01",))
        )
        self.assertEqual(created, 1)
        self.assertIn("dłuższy niż 40", errors[0])

    def test_receipt_and_issue_long_text(self):
        result = import_receipts(
            "r.csv", _csv(["indeks", "ilosc", "lot"], ("MAT-V", 5, "X" * 51)), self.user
        )
        self.assertEqual(result["created_hus"], 0)
        self.assertIn("partia", result["errors"][0])
        result = import_issue_orders(
            "i.csv",
            _csv(["indeks", "ilosc", "referencja"], ("MAT-V", 5, "R" * 101)),
            self.user,
        )
        self.assertEqual(result["lines"], 0)
        self.assertIn("referencja", result["errors"][0])


class ContentDispositionTests(_Base):
    """Kryterium 5: znaki specjalne w nazwie pliku etykiety."""

    def test_label_with_quote_and_newline(self):
        loc = Location.objects.create(code='Q"1\nX')
        hu = HandlingUnit.objects.create(
            number='HU"\n2', material=self.material, quantity=1
        )
        for url in (f"/lokalizacje/{loc.pk}/etykieta/", f"/hu/{hu.pk}/etykieta/"):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp["Content-Type"], "application/pdf")
                header = resp["Content-Disposition"]
                self.assertTrue(header.startswith("inline;"), header)
                self.assertNotIn("\n", header)

    def test_unicode_filename(self):
        loc = Location.objects.create(code="ŁÓDŹ-1")
        header = self.client.get(f"/lokalizacje/{loc.pk}/etykieta/")[
            "Content-Disposition"
        ]
        self.assertIn("filename*=utf-8''", header)
