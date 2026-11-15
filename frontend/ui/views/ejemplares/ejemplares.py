from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.api.client import ApiError
from frontend.ui import theme
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
    ejemplares = app.api.request("/api/ejemplar")
    books = app.api.request("/api/libro")
    sedes = app.api.request("/api/sede")
    id_ejemplares_disponibles = {
        ejemplar["id"] for ejemplar in app.api.request("/api/ejemplar/disponibilidad")
    }
    book_names = {book["id"]: book["titulo"] for book in books}
    sede_names = {sede["id"]: sede["nombre"] for sede in sedes}
    code_filter = text_input("Código", prefix_icon=ft.Icons.SEARCH, width=220)
    book_filter = text_input(
        "Libro", prefix_icon=ft.Icons.MENU_BOOK_OUTLINED, width=240
    )
    all_option = "__all__"
    physical_states = sorted(
        {item["estado_fisico"] for item in ejemplares}, key=str.casefold
    )
    physical_state_filter = ft.Dropdown(
        label="Estado físico",
        value=all_option,
        options=[
            ft.dropdown.Option(all_option, "Todos"),
            *[
                ft.dropdown.Option(state, state)
                for state in physical_states
            ],
        ],
        width=210,
        border_radius=10,
    )
    branch_filter = text_input(
        "Sede", prefix_icon=ft.Icons.LOCATION_ON_OUTLINED, width=220
    )
    result_count = ft.Text(color=theme.MUTED)
    table = ft.Container()

    def render_rows(_: Any = None) -> None:
        code = _normalize_text(code_filter.value)
        selected_book = _normalize_text(book_filter.value)
        selected_state = physical_state_filter.value
        selected_branch = _normalize_text(branch_filter.value)
        filtered = [
            ejemplar
            for ejemplar in ejemplares
            if code in _normalize_text(ejemplar["codigo"])
            and (
                not selected_book
                or selected_book
                in _normalize_text(book_names.get(ejemplar["libro_id"], ""))
            )
            and (
                selected_state == all_option
                or _normalize_text(ejemplar["estado_fisico"])
                == _normalize_text(selected_state)
            )
            and (
                not selected_branch
                or selected_branch
                in _normalize_text(sede_names.get(ejemplar["sede_id"], ""))
            )
        ]
        result_count.value = f"Mostrando {len(filtered)} de {len(ejemplares)} ejemplares"
        table.content = data_table(
            [
                "Código",
                "Libro",
                "Sede",
                "Estado físico",
                "Disponibilidad",
                "Acciones",
            ],
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
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip="Editar ejemplar",
                                on_click=lambda _, selected=ejemplar: (
                                    _edit_ejemplar(app, selected, books, sedes)
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip="Eliminar ejemplar",
                                on_click=lambda _, selected=ejemplar: (
                                    _confirm_delete_ejemplar(app, selected)
                                ),
                            ),
                        ],
                        spacing=0,
                    ),
                ]
                for ejemplar in filtered
            ],
        )
        app.page.update()

    for control in (
        code_filter,
        book_filter,
        physical_state_filter,
        branch_filter,
    ):
        control.on_change = render_rows
    render_rows()

    return ft.Column(
        [
            section_header(
                "Ejemplares",
                "Estado y ubicación del material bibliográfico.",
                "Registrar ejemplar",
                lambda _: _new_ejemplar(app),
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
                ft.Column(
                    [
                        ft.Row(
                            [
                                code_filter,
                                book_filter,
                                physical_state_filter,
                                branch_filter,
                            ],
                            spacing=12,
                            wrap=True,
                        ),
                        result_count,
                    ],
                    spacing=12,
                ),
                16,
            ),
            card(
                table,
                8,
            ),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _new_ejemplar(app: LibraryApp) -> None:
    try:
        books = app.api.request("/api/libro")
        sedes = app.api.request("/api/sede")
        estados = app.api.request("/api/estado/ejemplar")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    allowed_states = {
        "disponible",
        "no disponible",
        "danado",
        "extraviado",
        "destruido",
    }
    initial_states = [
        state
        for state in estados
        if _normalize_text(state["descripcion"]) in allowed_states
    ]
    initial_state = next(
        (
            state
            for state in initial_states
            if _normalize_text(state["descripcion"]) == "disponible"
        ),
        None,
    )
    if initial_state is None:
        notify(
            app.page,
            "No se encontró el estado inicial 'Disponible' en la API.",
            True,
        )
        return

    codigo = text_input("Código")
    estado_fisico = text_input("Estado físico", value="Bueno")
    book = text_input(
        "Libro (nombre exacto o ID)",
        hint_text="Ingresá el título exacto o el ID del libro",
    )
    branch = text_input(
        "Sede (nombre exacto o ID)",
        hint_text="Ingresá el nombre exacto o el ID de la sede",
    )
    state = ft.Dropdown(
        label="Estado del ejemplar",
        value=str(initial_state["id"]),
        options=[
            ft.dropdown.Option(str(item["id"]), item["descripcion"])
            for item in initial_states
        ],
        border_radius=10,
    )

    def submit() -> None:
        if not all(
            control.value.strip()
            for control in (codigo, estado_fisico, book, branch)
        ):
            notify(app.page, "Completá todos los campos.", True)
            return
        if not state.value:
            notify(app.page, "Seleccioná el estado del ejemplar.", True)
            return
        try:
            selected_book = _resolve_reference(
                book.value, books, "titulo", "libro"
            )
            selected_branch = _resolve_reference(
                branch.value, sedes, "nombre", "sede"
            )
            if not selected_branch.get("activa", False):
                raise ValueError("La sede seleccionada no está activa.")
            app.api.request(
                "/api/ejemplar",
                "POST",
                {
                    "codigo": codigo.value.strip(),
                    "estado_fisico": estado_fisico.value.strip(),
                    "estado_ejemplar_id": int(state.value),
                    "sede_id": selected_branch["id"],
                    "libro_id": selected_book["id"],
                },
            )
        except ValueError as error:
            notify(app.page, str(error), True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Ejemplar registrado correctamente.")
        app.navigate("Ejemplares")

    open_form(
        app.page,
        "Registrar ejemplar",
        [codigo, estado_fisico, book, branch, state],
        submit,
    )


def _edit_ejemplar(
    app: LibraryApp,
    ejemplar: dict[str, Any],
    books: list[dict[str, Any]],
    sedes: list[dict[str, Any]],
) -> None:
    codigo = text_input("Código", value=ejemplar["codigo"])
    estado_fisico = text_input("Estado físico", value=ejemplar["estado_fisico"])
    sede = ft.Dropdown(
        label="Sede",
        value=str(ejemplar["sede_id"]),
        options=[
            ft.dropdown.Option(str(item["id"]), item["nombre"])
            for item in sedes
        ],
        border_radius=10,
    )
    libro = ft.Dropdown(
        label="Libro",
        value=str(ejemplar["libro_id"]),
        options=[
            ft.dropdown.Option(str(item["id"]), item["titulo"])
            for item in books
        ],
        border_radius=10,
    )

    def submit() -> None:
        if not codigo.value.strip() or not estado_fisico.value.strip():
            notify(app.page, "Completá todos los campos.", True)
            return
        if not all(control.value for control in (sede, libro)):
            notify(app.page, "Seleccioná la sede y el libro.", True)
            return
        try:
            app.api.request(
                f"/api/ejemplar/{ejemplar['id']}",
                "PUT",
                {
                    "codigo": codigo.value.strip(),
                    "estado_fisico": estado_fisico.value.strip(),
                    "estado_ejemplar_id": ejemplar["estado_ejemplar_id"],
                    "sede_id": int(sede.value),
                    "libro_id": int(libro.value),
                },
            )
        except ValueError:
            notify(app.page, "Seleccioná valores válidos para sede y libro.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Ejemplar actualizado correctamente.")
        app.navigate("Ejemplares")

    open_form(
        app.page,
        f"Editar ejemplar #{ejemplar['id']}",
        [codigo, estado_fisico, sede, libro],
        submit,
    )


def _confirm_delete_ejemplar(
    app: LibraryApp, ejemplar: dict[str, Any]
) -> None:
    def delete(_: Any) -> None:
        try:
            app.api.request(f"/api/ejemplar/{ejemplar['id']}", "DELETE")
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Ejemplar eliminado correctamente.")
        app.navigate("Ejemplares")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Eliminar ejemplar"),
        content=ft.Text(
            f"¿Querés eliminar el ejemplar «{ejemplar['codigo']}»? "
            "No se puede eliminar si tiene préstamos, reservas o remitos asociados."
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton(
                "Eliminar ejemplar",
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=delete,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _resolve_reference(
    value: str,
    entities: list[dict[str, Any]],
    name_key: str,
    entity_name: str,
) -> dict[str, Any]:
    query = value.strip()
    if query.isdecimal():
        entity_id = int(query)
        match = next(
            (entity for entity in entities if entity["id"] == entity_id),
            None,
        )
        if match is None:
            raise ValueError(f"No existe {entity_name} con ID {entity_id}.")
        return match

    normalized_query = _normalize_text(query)
    matches = [
        entity
        for entity in entities
        if _normalize_text(entity[name_key]) == normalized_query
    ]
    if not matches:
        raise ValueError(
            f"No existe {entity_name} con ese nombre. "
            "Ingresá el nombre exacto o su ID."
        )
    if len(matches) > 1:
        raise ValueError(
            f"Hay varios resultados para ese {entity_name}; ingresá su ID."
        )
    return matches[0]
