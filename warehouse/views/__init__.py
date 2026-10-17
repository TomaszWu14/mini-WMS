"""Widoki ekranów operatora mini-WMS — pakiet podzielony wg obszarów (US-017).

`urls.py` odwołuje się do `views.<nazwa>`, więc każdy widok jest tu re-eksportowany.
Nowy ekran: dopisz go w module swojego obszaru i tutaj (oraz w macierzy dostępu i
`tests_urls.py`). Widoki skanera — osobno w `scanner_views.py`.
"""

from .dashboard import (
    _PLAN_STEPS,
    HEAT_CELLS_MAX,
    PLAN_MAX_ITEMS,
    _heat_level,
    _issue_progress,
    _location_heat,
    _movement_days,
    _today_plan,
    dashboard,
)
from .handling_units import (
    HU_LABELS_LIMIT,
    hu_allocate,
    hu_correct,
    hu_delivery,
    hu_detail,
    hu_label,
    hu_labels,
    hu_list,
    repack_view,
)
from .issues import (
    issue_add_line,
    issue_create,
    issue_detail,
    issue_execute,
    issue_import,
    issue_line_delete,
    issue_list,
    issue_pack,
    issue_pdf,
    issue_ship,
)
from .masterdata import (
    LOCATION_LABELS_LIMIT,
    _filtered_locations,
    location_create,
    location_import,
    location_label,
    location_labels,
    location_list,
    material_create,
    material_list,
)
from .movements import (
    _movement_export_rows,
    movement_export,
    movement_list,
)
from .receiving import (
    receive,
    receive_import,
)
from .reports import (
    report_index,
    report_locations,
    report_material_history,
)
from .stock import (
    _stock_export_rows,
    stock_by_location,
    stock_export,
    stock_import_view,
    stock_list,
)
from .stocktake import (
    inventory_view,
    stocktake_close,
    stocktake_create,
    stocktake_detail,
    stocktake_list,
    stocktake_save,
)
from .users import (
    PERMISSION_MATRIX,
    audit_log,
    login_log,
    user_create,
    user_edit,
    user_list,
)

__all__ = [
    "audit_log",
    "dashboard",
    "HEAT_CELLS_MAX",
    "_heat_level",
    "_location_heat",
    "_issue_progress",
    "PLAN_MAX_ITEMS",
    "_PLAN_STEPS",
    "_today_plan",
    "_movement_days",
    "material_list",
    "material_create",
    "LOCATION_LABELS_LIMIT",
    "_filtered_locations",
    "location_list",
    "location_create",
    "location_import",
    "location_label",
    "location_labels",
    "receive",
    "receive_import",
    "hu_list",
    "hu_detail",
    "hu_label",
    "HU_LABELS_LIMIT",
    "hu_labels",
    "hu_allocate",
    "hu_delivery",
    "hu_correct",
    "repack_view",
    "issue_list",
    "issue_create",
    "issue_detail",
    "issue_add_line",
    "issue_line_delete",
    "issue_execute",
    "issue_pack",
    "issue_ship",
    "issue_import",
    "issue_pdf",
    "stock_list",
    "stock_by_location",
    "stock_import_view",
    "_stock_export_rows",
    "stock_export",
    "stocktake_list",
    "stocktake_create",
    "stocktake_detail",
    "stocktake_save",
    "stocktake_close",
    "inventory_view",
    "movement_list",
    "_movement_export_rows",
    "movement_export",
    "PERMISSION_MATRIX",
    "user_list",
    "login_log",
    "user_create",
    "user_edit",
    "report_index",
    "report_locations",
    "report_material_history",
]
