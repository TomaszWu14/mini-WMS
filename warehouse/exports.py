"""Eksport stanów i ruchów do CSV oraz XLSX."""

import csv
import io

# Znaki, od których arkusz kalkulacyjny może zinterpretować komórkę jako formułę
# (CSV/Formula Injection). Wartości tekstowe zaczynające się od nich poprzedzamy
# apostrofem, by Excel/LibreOffice potraktował je jako zwykły tekst.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value):
    if isinstance(value, str) and value[:1] in _FORMULA_PREFIXES:
        return "'" + value
    return value


def rows_to_csv_response(filename: str, header, rows):
    """Buduje HttpResponse CSV (UTF-8 z BOM dla Excela)."""
    from django.http import HttpResponse

    buffer = io.StringIO()
    buffer.write("﻿")  # BOM, aby Excel poprawnie odczytał polskie znaki
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe_cell(v) for v in row])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    return response


def rows_to_xlsx_response(filename: str, header, rows, sheet_title="Dane"):
    """Buduje HttpResponse XLSX."""
    from django.http import HttpResponse
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.append(list(header))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append([_safe_cell(v) for v in row])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response
