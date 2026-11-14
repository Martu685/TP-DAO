from __future__ import annotations

from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.api.client import ApiError
from frontend.ui.components import (
    card,
    data_table,
    notify,
    open_form,
    section_header,
    text_input,
)

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    books = app.api.request("/api/libro")
    search = text_input(
        "Buscar por título, autor o ISBN", prefix_icon=ft.Icons.SEARCH
    )
    table = ft.Container()

    def render_rows(_: Any = None) -> None:
        term = search.value.strip().casefold()
        filtered = [
            book
            for book in books
            if term
            in " ".join(
                [book["titulo"], book["isbn"], book["editorial"], *book["autores"]]
            ).casefold()
        ]
        table.content = data_table(
            ["Libro", "ISBN", "Autores", "Editorial", "Año"],
            [
                [
                    ft.Text(book["titulo"], weight=ft.FontWeight.W_500),
                    ft.Text(book["isbn"]),
                    ft.Text(", ".join(book["autores"])),
                    ft.Text(book["editorial"]),
                    ft.Text(str(book["año_publicacion"])),
                ]
                for book in filtered
            ],
        )
        app.page.update()

    search.on_change = render_rows
    view = ft.Column(
        [
            section_header(
                "Catálogo de libros",
                "Administrá el catálogo de la biblioteca.",
                "Nuevo libro",
                lambda _: _new_book(app),
            ),
            card(search, 12),
            card(table, 8),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
    render_rows()
    return view


def _new_book(app: LibraryApp) -> None:
    isbn = text_input("ISBN")
    title = text_input("Título")
    authors = text_input("Autores", hint_text="Separá cada autor con una coma")
    publisher = text_input("Editorial")
    year = text_input("Año de publicación", keyboard_type=ft.KeyboardType.NUMBER)

    def submit() -> None:
        if not all(
            field.value.strip() for field in (isbn, title, authors, publisher, year)
        ):
            notify(app.page, "Completá todos los campos.", True)
            return
        try:
            app.api.request(
                "/api/libro",
                "POST",
                {
                    "isbn": isbn.value.strip(),
                    "titulo": title.value.strip(),
                    "autores": [
                        author.strip()
                        for author in authors.value.split(",")
                        if author.strip()
                    ],
                    "editorial": publisher.value.strip(),
                    "año_publicacion": int(year.value),
                },
            )
        except ValueError:
            notify(app.page, "El año de publicación debe ser un número.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Libro agregado al catálogo.")
        app.navigate("Libros")

    open_form(app.page, "Agregar libro", [isbn, title, authors, publisher, year], submit)
