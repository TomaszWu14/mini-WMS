"""Testy poprawek importu lokalizacji: pojemność 0 = bez limitu, atomowość."""

from unittest.mock import patch

from django.test import TestCase

from .imports import import_locations
from .models import Location


class LocationImportCapacityTests(TestCase):
    def test_capacity_zero_is_no_limit(self):
        data = b"kod;typ;pojemnosc\nA-1;ZAPAS;0\n"
        created, updated, errors = import_locations("loc.csv", data)
        self.assertEqual((created, updated, errors), (1, 0, []))
        self.assertEqual(Location.objects.get(code="A-1").capacity, 0)

    def test_capacity_empty_defaults_to_one(self):
        data = b"kod;typ;pojemnosc\nA-2;ZAPAS;\n"
        created, updated, errors = import_locations("loc.csv", data)
        self.assertEqual((created, updated, errors), (1, 0, []))
        self.assertEqual(Location.objects.get(code="A-2").capacity, 1)

    def test_negative_capacity_skips_row_with_error(self):
        data = b"kod;typ;pojemnosc\nA-3;ZAPAS;-1\nA-4;ZAPAS;2\n"
        created, updated, errors = import_locations("loc.csv", data)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("A-3", errors[0])
        self.assertIn("Niepoprawna pojemność", errors[0])
        self.assertFalse(Location.objects.filter(code="A-3").exists())
        self.assertEqual(Location.objects.get(code="A-4").capacity, 2)

    def test_import_is_atomic_on_crash(self):
        data = b"kod;typ;pojemnosc\nB-1;ZAPAS;1\nB-2;ZAPAS;1\n"
        with (
            patch(
                "warehouse.imports.Location.objects.update_or_create",
                side_effect=[(Location(code="B-1"), True), RuntimeError("boom")],
            ),
            self.assertRaises(RuntimeError),
        ):
            import_locations("loc.csv", data)
        self.assertEqual(Location.objects.count(), 0)
