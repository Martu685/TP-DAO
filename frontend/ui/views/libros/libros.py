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
    update_form_errors,
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
            ["Libro", "ISBN", "Autores", "Editorial", "Año", "Acciones"],
            [
                [
                    ft.Text(book["titulo"], weight=ft.FontWeight.W_500),
                    ft.Text(book["isbn"]),
                    ft.Text(", ".join(book["autores"])),
                    ft.Text(book["editorial"]),
                    ft.Text(str(book["año_publicacion"])),
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip="Editar libro",
                                on_click=lambda _, selected=book: _edit_book(
                                    app, selected
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip="Eliminar libro",
                                on_click=lambda _, selected=book: (
                                    _confirm_delete_book(app, selected)
                                ),
                            ),
                        ],
                        spacing=0,
                    ),
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
        fields = [isbn, title, authors, publisher, year]
        errors = [
            (field, "Completá este campo.")
            for field in fields
            if not field.value.strip()
        ]
        if update_form_errors(app.page, fields, errors):
            return
        try:
            publication_year = int(year.value)
        except ValueError:
            update_form_errors(
                app.page,
                fields,
                [(year, "El año de publicación debe ser un número.")],
            )
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
                    "año_publicacion": publication_year,
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Libro agregado al catálogo.")
        app.navigate("Libros")

    open_form(app.page, "Agregar libro", [isbn, title, authors, publisher, year], submit)


def _edit_book(app: LibraryApp, book: dict[str, Any]) -> None:
    isbn = text_input("ISBN", value=book["isbn"])
    title = text_input("Título", value=book["titulo"])
    authors = text_input(
        "Autores",
        value=", ".join(book["autores"]),
        hint_text="Separá cada autor con una coma",
    )
    publisher = text_input("Editorial", value=book["editorial"])
    year = text_input(
        "Año de publicación",
        value=str(book["año_publicacion"]),
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    def submit() -> None:
        fields = [isbn, title, authors, publisher, year]
        errors = [
            (field, "Completá este campo.")
            for field in fields
            if not field.value.strip()
        ]
        if update_form_errors(app.page, fields, errors):
            return
        try:
            publication_year = int(year.value)
        except ValueError:
            update_form_errors(
                app.page,
                fields,
                [(year, "El año de publicación debe ser un número.")],
            )
            return
        try:
            app.api.request(
                f"/api/libro/{book['id']}",
                "PUT",
                {
                    "isbn": isbn.value.strip(),
                    "titulo": title.value.strip(),
                    "autores": [
                        author.strip()
                        for author in authors.value.split(",")
                        if author.strip()
                    ],
                    "editorial": publisher.value.strip(),
                    "año_publicacion": publication_year,
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Libro actualizado correctamente.")
        app.navigate("Libros")

    open_form(
        app.page,
        f"Editar libro #{book['id']}",
        [isbn, title, authors, publisher, year],
        submit,
    )


def _confirm_delete_book(app: LibraryApp, book: dict[str, Any]) -> None:
    def delete(_: Any) -> None:
        try:
            app.api.request(f"/api/libro/{book['id']}", "DELETE")
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Libro eliminado correctamente.")
        app.navigate("Libros")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Eliminar libro"),
        content=ft.Text(
            f"¿Querés eliminar «{book['titulo']}»? "
            "No se puede eliminar si tiene ejemplares registrados."
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton(
                "Eliminar libro",
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=delete,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)
