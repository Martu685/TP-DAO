from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from frontend.ui import theme
from frontend.ui.components import card, data_table, section_header

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    ejemplares = app.api.request("/api/ejemplar")
    books = app.api.request("/api/libro")
    sedes = app.api.request("/api/sede")
    id_ejemplares_disponibles = {
        ejemplar["id"] for ejemplar in app.api.request("/api/ejemplar/disponibilidad")
    }
    book_names = {book["id"]: book["titulo"] for book in books}
    sede_names = {sede["id"]: sede["nombre"] for sede in sedes}

    return ft.Column(
        [
            section_header(
                "Ejemplares", "Estado y ubicación del material bibliográfico."
            ),
            ft.Row(
                [
                    ft.Text(f"{len(ejemplares)} ejemplares registrados", color=theme.MUTED),
                    ft.Container(expand=True),
                    ft.Text(
                        f"{len(id_ejemplares_disponibles)} disponibles",
                        color=theme.ACCENT,
                        weight=ft.FontWeight.W_600,
                    ),
                ]
            ),
            card(
                data_table(
                    ["Código", "Libro", "Sede", "Estado físico", "Disponibilidad"],
                    [
                        [
                            ft.Text(ejemplar["codigo"], weight=ft.FontWeight.W_500),
                            ft.Text(book_names.get(ejemplar["libro_id"], "—")),
                            ft.Text(sede_names.get(ejemplar["sede_id"], "—")),
                            ft.Text(ejemplar["estado_fisico"]),
                            ft.Container(
                                content=ft.Text(
                                    "Disponible"
                                    if ejemplar["id"] in id_ejemplares_disponibles
                                    else "No disponible",
                                    size=12,
                                    color=theme.ACCENT
                                    if ejemplar["id"] in id_ejemplares_disponibles
                                    else theme.MUTED,
                                ),
                                bgcolor="#EAF2ED"
                                if ejemplar["id"] in id_ejemplares_disponibles
                                else "#F0F1F3",
                                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                                border_radius=20,
                            ),
                        ]
                        for ejemplar in ejemplares
                    ],
                ),
                8,
            ),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
