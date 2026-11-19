from __future__ import annotations

from typing import TYPE_CHECKING, Any

import flet as ft
from datetime import date

from frontend.api.client import ApiError
from frontend.ui.components import card, data_table, empty_state, section_header

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


REPORTS = (
    ("Préstamos activos", "/api/reportes/prestamos-activos"),
    ("Préstamos vencidos", "/api/reportes/prestamos-vencidos"),
    ("Libros más solicitados", "/api/reportes/libros-mas-solicitados"),
    ("Disponibilidad por sede", "/api/reportes/disponibilidad-por-sede"),
    ("Material en tránsito", "/api/reportes/material-en-transito"),
)


def build(app: LibraryApp) -> ft.Control:
    selector = ft.Dropdown(
        label="Reporte",
        value=REPORTS[0][1],
        options=[
            ft.dropdown.Option(endpoint, label)
            for label, endpoint in REPORTS
        ],
        border_radius=10,
        width=300,
    )
    table = ft.Container()

    def display_report(event: Any = None) -> None:
        endpoint = event.control.value if event is not None else selector.value
        try:
            rows = app.api.request(endpoint)
        except ApiError as error:
            table.content = empty_state(
                f"No se pudo cargar el reporte: {error}",
                ft.Icons.CLOUD_OFF_OUTLINED,
            )
            app.page.update()
            return

        columns = list(dict.fromkeys(key for row in rows for key in row))
        if not columns:
            table.content = empty_state(
                (
                    "Todavía no hay préstamos ni reservas para calcular las solicitudes."
                    if endpoint == "/api/reportes/libros-mas-solicitados"
                    else "No hay datos para este reporte."
                ),
                ft.Icons.QUERY_STATS_OUTLINED,
            )
        else:
            table.content = data_table(
                [_column_label(column) for column in columns],
                [
                    [_cell_text(column, row[column]) for column in columns]
                    for row in rows
                ],
                expand=False,
            )
            table.content = ft.Row(
                [table.content],
                scroll=ft.ScrollMode.AUTO,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        app.page.update()

    selector.on_select = display_report
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


def _column_label(column: str) -> str:
    labels = {
        "prestamo_id": "Préstamo",
        "ejemplar_id": "Ejemplar",
        "libro_id": "Libro ID",
        "codigo_ejemplar": "Código",
        "socio_id": "Socio",
        "sede_origen_id": "Sede origen",
        "sede_destino_id": "Sede destino",
        "fecha_inicio": "Inicio",
        "fecha_vencimiento": "Vencimiento",
        "fecha_emision": "Emisión",
        "fecha_recepcion": "Recepción",
        "tiempo_promedio_dias": "Promedio (días)",
        "tasa_envios_exitosos": "Envíos exitosos (%)",
        "promedio_transito_dias": "Tránsito promedio (días)",
    }
    return labels.get(column, column.replace("_", " ").capitalize())


def _cell_text(column: str, value: Any) -> ft.Text:
    if isinstance(value, list):
        display_value = ", ".join(str(item) for item in value)
    elif value is None:
        display_value = "—"
    elif column.startswith("fecha_"):
        try:
            display_value = date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
        except ValueError:
            display_value = str(value)
    elif column.endswith("_id") and isinstance(value, int):
        display_value = f"#{value}"
    else:
        display_value = str(value)
    return ft.Text(display_value, no_wrap=True)
