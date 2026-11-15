from __future__ import annotations

from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.ui import theme
from frontend.ui.components import card, data_table, section_header

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    books = app.api.request("/api/libro")
    socios = app.api.request("/api/socio")
    ejemplares = app.api.request("/api/ejemplar")
    prestamos = app.api.request("/api/prestamo")
    contador_ejemplares_disponibles = len(app.api.request("/api/ejemplar/disponibilidad"))
    prestamos_activos = [prestamo for prestamo in prestamos if prestamo.get("fecha_devolucion") is None]

    metrics = [
        ("Libros en catálogo", len(books), ft.Icons.MENU_BOOK_OUTLINED, "#EAF2ED"),
        ("Socios registrados", len(socios), ft.Icons.GROUP_OUTLINED, "#EEF0FA"),
        (
            "Ejemplares disponibles",
            contador_ejemplares_disponibles,
            ft.Icons.INVENTORY_2_OUTLINED,
            "#FBF2E5",
        ),
        (
            "Préstamos activos",
            len(prestamos_activos),
            ft.Icons.SWAP_HORIZ_OUTLINED,
            "#F8EDEE",
        ),
    ]
    metric_cards = [_metric_card(*metric) for metric in metrics]

    ejemplares_by_id = {ejemplar["id"]: ejemplar for ejemplar in ejemplares}
    books_by_id = {book["id"]: book for book in books}
    prestamos_recientes = sorted(
        prestamos_activos, key=lambda prestamo: prestamo["fecha_inicio"], reverse=True
    )[:5]
    return ft.Column(
        [
            section_header("Buen día 👋", "Un resumen de la actividad de tu biblioteca."),
            ft.Row(metric_cards, spacing=14, wrap=True),
            card(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    "Préstamos recientes",
                                    size=17,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Container(expand=True),
                                ft.TextButton(
                                    "Ver todos",
                                    on_click=lambda _: app.navigate("Préstamos"),
                                ),
                            ]
                        ),
                        data_table(
                            ["N.º", "Libro", "Ejemplar", "Vencimiento"],
                            [
                                [
                                    ft.Text(f"#{prestamo['id']}"),
                                    ft.Text(
                                        books_by_id.get(
                                            ejemplares_by_id.get(
                                                prestamo["ejemplar_id"], {}
                                            ).get("libro_id"),
                                            {},
                                        ).get("titulo", "Libro"),
                                        weight=ft.FontWeight.W_500,
                                    ),
                                    ft.Text(
                                        ejemplares_by_id.get(
                                            prestamo["ejemplar_id"], {}
                                        ).get("codigo", "—")
                                    ),
                                    ft.Text(prestamo["fecha_vencimiento"]),
                                ]
                                for prestamo in prestamos_recientes
                            ],
                        ),
                    ],
                    spacing=14,
                ),
                20,
            ),
        ],
        spacing=20,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _metric_card(
    label: str, value: int, icon: Any, tint: str
) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(label, size=13, color=theme.MUTED, expand=True),
                        ft.Container(
                            content=ft.Icon(icon, color=theme.ACCENT, size=18),
                            bgcolor=tint,
                            padding=9,
                            border_radius=10,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                ft.Text(
                    str(value),
                    size=30,
                    weight=ft.FontWeight.BOLD,
                    color=theme.INK,
                ),
            ],
            spacing=15,
        ),
        width=220,
        padding=20,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=14,
    )
