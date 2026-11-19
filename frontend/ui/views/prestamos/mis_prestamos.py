from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from frontend.ui import theme
from frontend.ui.components import card, data_table, empty_state, section_header

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    loans = app.api.request("/api/prestamo-local")
    books = app.api.request("/api/libro")
    copies = app.api.request("/api/ejemplar")
    states = app.api.request("/api/estado/prestamo")
    book_names = {book["id"]: book["titulo"] for book in books}
    copies_by_id = {copy["id"]: copy for copy in copies}
    state_names = {state["id"]: state["descripcion"] for state in states}

    rows: list[list[ft.Control]] = []
    for loan in loans:
        copy = copies_by_id.get(loan["ejemplar_id"], {})
        rows.append(
            [
                ft.Text(f"#{loan['id']}"),
                ft.Text(
                    (
                        f"{book_names.get(copy.get('libro_id'), 'Libro')} · "
                        f"{copy.get('codigo', '—')}"
                    ),
                    weight=ft.FontWeight.W_500,
                ),
                ft.Text(str(loan["fecha_inicio"])),
                ft.Text(str(loan["fecha_vencimiento"])),
                ft.Text(
                    state_names.get(loan["estado_prestamo_id"], "Desconocido"),
                    color=theme.ACCENT,
                ),
                ft.Text(str(loan["fecha_devolucion"] or "Pendiente")),
            ]
        )
    table = (
        data_table(
            ["N.º", "Libro / ejemplar", "Inicio", "Vencimiento", "Estado", "Devolución"],
            rows,
        )
        if rows
        else empty_state(
            "Todavía no tenés préstamos registrados.",
            ft.Icons.SWAP_HORIZ_OUTLINED,
        )
    )

    return ft.Column(
        [
            section_header(
                "Mis préstamos",
                "Consultá el estado y las fechas de tus préstamos.",
            ),
            card(table, 8),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
