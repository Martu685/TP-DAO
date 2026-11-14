from __future__ import annotations

from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.ui.components import card, data_table, empty_state, section_header

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


REPORTS = {
    "Préstamos activos": "/api/reportes/prestamos-activos",
    "Préstamos vencidos": "/api/reportes/prestamos-vencidos",
    "Libros más solicitados": "/api/reportes/libros-mas-solicitados",
    "Disponibilidad por sede": "/api/reportes/disponibilidad-por-sede",
    "Material en tránsito": "/api/reportes/material-en-transito",
}


def build(app: LibraryApp) -> ft.Control:
    selector = ft.Dropdown(
        label="Reporte",
        value="Préstamos activos",
        options=[ft.dropdown.Option(label, label) for label in REPORTS],
        border_radius=10,
        width=300,
    )
    table = ft.Container()

    def display_report(_: Any = None) -> None:
        rows = app.api.request(REPORTS[selector.value])
        columns = list(dict.fromkeys(key for row in rows for key in row))
        if not columns:
            table.content = empty_state(
                "No hay datos para este reporte.", ft.Icons.QUERY_STATS_OUTLINED
            )
        else:
            table.content = data_table(
                [column.replace("_", " ").capitalize() for column in columns],
                [
                    [_cell_text(row[column]) for column in columns]
                    for row in rows
                ],
            )
        app.page.update()

    selector.on_change = display_report
    display_report()
    return ft.Column(
        [
            section_header(
                "Reportes", "Consultá el estado y los movimientos de la biblioteca."
            ),
            card(selector, 12),
            card(table, 8),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _cell_text(value: Any) -> ft.Text:
    if isinstance(value, list):
        display_value = ", ".join(str(item) for item in value)
    else:
        display_value = str(value) if value is not None else "—"
    return ft.Text(display_value)
