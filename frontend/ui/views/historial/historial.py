from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.ui import theme
from frontend.ui.components import card, data_table, empty_state, section_header, text_input

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    history = app.api.request("/api/historial-lecturas")
    socios = app.api.request("/api/socio")
    books = app.api.request("/api/libro")
    socios_by_id = {socio["id"]: socio for socio in socios}
    books_by_id = {book["id"]: book for book in books}

    socio_filter = text_input(
        "Buscar socio por nombre, DNI o email",
        prefix_icon=ft.Icons.PERSON_SEARCH_OUTLINED,
        expand=True,
    )
    book_filter = text_input(
        "Buscar libro por título, autor o ISBN",
        prefix_icon=ft.Icons.MENU_BOOK_OUTLINED,
        expand=True,
    )
    summary = ft.Text(color=theme.MUTED)
    table = ft.Container()

    def render_rows(_: Any = None) -> None:
        socio_term = _normalize(socio_filter.value)
        book_term = _normalize(book_filter.value)
        matching = []

        for entry in history:
            socio = socios_by_id.get(entry["socio_id"], {})
            book = books_by_id.get(entry["libro_id"], {})
            socio_text = " ".join(
                str(value)
                for value in (
                    socio.get("nombre", ""),
                    socio.get("apellido", ""),
                    socio.get("dni", ""),
                    socio.get("email", ""),
                )
            )
            book_text = " ".join(
                [
                    str(book.get("titulo", "")),
                    str(book.get("isbn", "")),
                    *book.get("autores", []),
                ]
            )
            if socio_term in _normalize(socio_text) and book_term in _normalize(
                book_text
            ):
                matching.append((entry, socio, book))

        reader_count = len({entry["socio_id"] for entry, _, _ in matching})
        summary.value = f"{len(matching)} lecturas · {reader_count} socios"
        if not history:
            table.content = empty_state(
                "Todavía no hay lecturas registradas.",
                ft.Icons.HISTORY_OUTLINED,
            )
        elif not matching:
            table.content = empty_state(
                "No hay lecturas que coincidan con los filtros.",
                ft.Icons.SEARCH_OFF_OUTLINED,
            )
        else:
            table.content = data_table(
                ["Fecha", "Socio", "DNI", "Libro", "Préstamo"],
                [
                    [
                        ft.Text(entry["fecha"]),
                        ft.Text(
                            _socio_name(socio, entry["socio_id"]),
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.Text(str(socio.get("dni", "—"))),
                        ft.Text(
                            book.get("titulo", f"Libro #{entry['libro_id']}"),
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.Text(
                            f"#{entry['prestamo_id']}"
                            if entry.get("prestamo_id") is not None
                            else "—"
                        ),
                    ]
                    for entry, socio, book in matching
                ],
            )
        app.page.update()

    socio_filter.on_change = render_rows
    book_filter.on_change = render_rows
    render_rows()

    return ft.Column(
        [
            section_header(
                "Historial de lecturas",
                "Consultá los libros leídos por cada socio.",
            ),
            card(
                ft.Row([socio_filter, book_filter], spacing=12),
                12,
            ),
            summary,
            card(table, 8),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _socio_name(socio: dict[str, Any], socio_id: int) -> str:
    name = f"{socio.get('nombre', '')} {socio.get('apellido', '')}".strip()
    return name or f"Socio #{socio_id}"
