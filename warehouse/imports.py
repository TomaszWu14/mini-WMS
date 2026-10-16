"""Import lokalizacji z pliku CSV lub XLSX.

Oczekiwane kolumny (nagłówki, wielkość liter bez znaczenia):
    kod         — wymagany, unikalny kod lokalizacji (np. A-01-01A)
    typ         — opcjonalny: PICKING albo ZAPAS (domyślnie ZAPAS)
    pojemnosc   — opcjonalna liczba HU (domyślnie 1, 0 = bez limitu)
"""

import csv
import io
import zipfile
import zlib
from itertools import islice
from xml.etree.ElementTree import ParseError

from django.conf import settings
from django.db import transaction

from .models import Location, LocationType


class ImportError_(Exception):
    """Błąd importu pliku lokalizacji."""


def parse_int_cell(value):
    """Parsuje liczbę całkowitą z komórki: obsługuje '5', '5.0', '5,0'
    (przecinek dziesiętny po polsku), spacje i separatory tysięcy. Zwraca
    None dla pustych/'-', podnosi ValueError dla śmieci."""
    if value is None:
        return None
    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    if text in ("", "-", "–", "—"):
        return None
    return int(float(text.replace(",", ".")))


def get_or_create_ci(model, field: str, value: str, defaults=None):
    """get_or_create nieczułe na wielkość liter (po `field`) — żeby 'B0-1' i
    'b0-1' nie tworzyły dwóch rekordów tej samej lokalizacji/materiału."""
    obj = model.objects.filter(**{f"{field}__iexact": value}).first()
    if obj is not None:
        return obj, False
    return model.objects.create(**{field: value}, **(defaults or {})), True


def _normalize_type(value: str) -> str:
    value = (value or "").strip().upper()
    if value in {LocationType.PICKING, "PICK", "P"}:
        return LocationType.PICKING
    if value in {"", LocationType.ZAPAS, "ZAP", "Z", "STORAGE"}:
        return LocationType.ZAPAS
    raise ImportError_(f"Nieznany typ lokalizacji: '{value}'.")


def _parse_capacity(value) -> int:
    """0 = bez limitu (jak w LocationForm/modelu) — zostaje, nie jest
    podnoszone do 1. Ujemne wartości to błąd wiersza importu."""
    if value in (None, ""):
        return 1
    try:
        capacity = int(float(str(value).strip()))
    except (TypeError, ValueError) as exc:
        raise ImportError_(f"Niepoprawna pojemność: '{value}'.") from exc
    if capacity < 0:
        raise ImportError_(f"Niepoprawna pojemność: '{value}'.")
    return capacity


def _decode_csv(data: bytes) -> str:
    """Dekoduje plik CSV. Polski Excel zapisuje często w cp1250/latin2 —
    po nieudanym UTF-8 próbujemy tych kodowań zamiast wywracać cały import."""
    for encoding in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Ostatnia deska ratunku — nie trać danych przez pojedynczy zły bajt.
    return data.decode("utf-8", errors="replace")


def _rows_from_csv(data: bytes):
    text = _decode_csv(data)
    # Wykryj separator (przecinek lub średnik).
    sample = text[:1024]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    for row in reader:
        yield {(k or "").strip().lower(): v for k, v in row.items()}


# Wyjątki, którymi openpyxl/zipfile/XML sygnalizują uszkodzony lub wrogi plik
# (defusedxml rzuca podklasy ValueError). Inne błędy to bugi — nie maskujemy ich.
_XLSX_ERRORS = (
    zipfile.BadZipFile,
    KeyError,
    ValueError,
    EOFError,
    zlib.error,
    ParseError,
    RuntimeError,  # zipfile: zaszyfrowany członek archiwum
    NotImplementedError,  # zipfile: nieobsługiwana metoda kompresji
)
# Importy używają kilku kolumn; dalsze są ignorowane, żeby szeroki arkusz
# (16 384 kolumny × tysiące wierszy) nie zajął gigabajtów pamięci.
XLSX_MAX_COLUMNS = 50
_ZIP_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_XLSX_BROKEN = (
    "Plik nie jest poprawnym XLSX — zapisz go ponownie w Excelu albo użyj CSV."
)


def _check_xlsx_archive(data: bytes) -> None:
    """Odrzuca plik przed `load_workbook`: brak sygnatury ZIP, uszkodzone archiwum
    albo za duża suma rozmiarów po rozpakowaniu. `zipfile` nie rozpakuje członka
    ponad zadeklarowany `file_size`, więc suma deklaracji ogranicza pamięć."""
    if not data.startswith(b"PK\x03\x04"):
        raise ImportError_(_XLSX_BROKEN)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            members = zf.infolist()
    except (zipfile.BadZipFile, zlib.error, EOFError, ValueError) as exc:
        raise ImportError_(_XLSX_BROKEN) from exc
    # Excel zapisuje XLSX bez szyfrowania ZIP i tylko metodą STORED/DEFLATED.
    if any(m.flag_bits & 0x1 or m.compress_type not in _ZIP_METHODS for m in members):
        raise ImportError_(_XLSX_BROKEN)
    total = sum(m.file_size for m in members)
    limit = settings.IMPORT_MAX_UNCOMPRESSED_BYTES
    if total > limit:
        raise ImportError_(
            f"Plik XLSX po rozpakowaniu przekracza {limit // (1024 * 1024)} MB — "
            "podziel go na mniejsze albo użyj CSV."
        )


def _rows_from_xlsx(data: bytes):
    """Generator wierszy; pusty wiersz daje `None`, żeby liczył się do limitu
    odczytu w `parse_locations_file` — inaczej arkusz z „dziurą” do wiersza
    1 048 576 przechodziłby milion pustych wierszy, zanim limit zadziała."""
    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException

    _check_xlsx_archive(data)
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            raise ImportError_(_XLSX_BROKEN)
        rows = ws.iter_rows(max_col=XLSX_MAX_COLUMNS, values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            return
        columns = [
            (i, str(h).strip().lower()) for i, h in enumerate(header) if h is not None
        ]
        for row in rows:
            if row is None or all(c is None for c in row):
                yield None
                continue
            # Wiersze krótsze od nagłówka (puste komórki z prawej) nie mogą rzucać
            # IndexError i wywracać całego importu — brakujące kolumny → None.
            yield {name: (row[i] if i < len(row) else None) for i, name in columns}
    except (InvalidFileException, *_XLSX_ERRORS) as exc:
        raise ImportError_(_XLSX_BROKEN) from exc


def parse_locations_file(filename: str, data: bytes):
    """Zwraca listę słowników wierszy z pliku CSV/XLSX."""
    lower = filename.lower()
    if lower.endswith(".csv"):
        gen = _rows_from_csv(data)
    elif lower.endswith((".xlsx", ".xlsm")):
        gen = _rows_from_xlsx(data)
    else:
        raise ImportError_("Obsługiwane formaty to .csv oraz .xlsx.")
    # Czytamy najwyżej limit+1 wierszy — mały XLSX potrafi rozpakować się do
    # milionów wierszy, a jeden plik nie może zająć całej pamięci procesu.
    if settings.DEMO_MODE:
        limit = settings.DEMO_IMPORT_MAX_ROWS
        message = f"W wersji demo import obejmuje najwyżej {limit} wierszy."
    else:
        limit = settings.IMPORT_MAX_ROWS
        message = f"Import obejmuje najwyżej {limit} wierszy — podziel plik; nic nie zapisano."
    rows = list(islice(gen, limit + 1))
    if len(rows) > limit:
        raise ImportError_(message)
    return [row for row in rows if row is not None]


@transaction.atomic
def import_locations(filename: str, data: bytes):
    """Importuje lokalizacje. Zwraca (utworzone, zaktualizowane, błędy)."""
    rows = parse_locations_file(filename, data)
    created = updated = 0
    errors: list[str] = []

    for i, row in enumerate(rows, start=2):  # wiersz 1 to nagłówek
        code = str(row.get("kod") or row.get("code") or "").strip()
        if not code:
            errors.append(f"Wiersz {i}: brak kodu lokalizacji — pominięto.")
            continue
        try:
            loc_type = _normalize_type(str(row.get("typ") or row.get("type") or ""))
            capacity = _parse_capacity(
                row.get("pojemnosc") or row.get("pojemność") or row.get("capacity")
            )
        except ImportError_ as exc:
            errors.append(f"Wiersz {i} ({code}): {exc}")
            continue

        obj, was_created = Location.objects.update_or_create(
            code=code,
            defaults={"type": loc_type, "capacity": capacity},
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return created, updated, errors
