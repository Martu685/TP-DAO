from __future__ import annotations

from datetime import date, timedelta
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
    prestamos = app.api.request("/api/prestamo")
    ejemplares = app.api.request("/api/ejemplar")
    books = app.api.request("/api/libro")
    states = app.api.request("/api/estado/prestamo")
    ejemplares_by_id = {item["id"]: item for item in ejemplares}
    book_names = {book["id"]: book["titulo"] for book in books}
    state_names = {state["id"]: state["descripcion"] for state in states}

    return ft.Column(
        [
            section_header(
                "Préstamos",
                "Seguimiento de préstamos y devoluciones.",
                "Nuevo préstamo",
                lambda _: _new_prestamo(app),
            ),
            card(
                data_table(
                    ["N.º", "Libro / ejemplar", "Inicio", "Vencimiento", "Estado", "Acción"],
                    [
                        _prestamo_row(
                            app, prestamo, ejemplares_by_id, book_names, state_names
                        )
                        for prestamo in prestamos
                    ],
                ),
                8,
            ),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _prestamo_row(
    app: LibraryApp,
    prestamo: dict[str, Any],
    ejemplares_by_id: dict[int, dict[str, Any]],
    book_names: dict[int, str],
    state_names: dict[int, str],
) -> list[ft.Control]:
    copy = ejemplares_by_id.get(prestamo["ejemplar_id"], {})
    can_return = (
        prestamo.get("fecha_devolucion") is None
        and prestamo.get("tipo_prestamo") == "prestamo_local"
    )
    action: ft.Control
    if can_return:
        action = ft.TextButton(
            "Registrar devolución",
            icon=ft.Icons.KEYBOARD_RETURN,
            on_click=lambda _, selected=prestamo: _return_prestamo(app, selected),
        )
    else:
        action = ft.Text(
            "Finalizado" if prestamo.get("fecha_devolucion") else "Interbibliotecario",
            color=theme.MUTED,
        )
    return [
        ft.Text(f"#{prestamo['id']}"),
        ft.Text(
            f"{book_names.get(copy.get('libro_id'), 'Libro')} · "
            f"{copy.get('codigo', '—')}",
            weight=ft.FontWeight.W_500,
        ),
        ft.Text(prestamo["fecha_inicio"]),
        ft.Text(prestamo["fecha_vencimiento"]),
        ft.Text(state_names.get(prestamo["estado_prestamo_id"], "—")),
        action,
    ]


def _new_prestamo(app: LibraryApp) -> None:
    try:
        members = [
            member
            for member in app.api.request("/api/socio")
            if member["habilitado"]
        ]
        branches = [
            branch
            for branch in app.api.request("/api/sede")
            if branch["activa"]
        ]
        ejemplares = app.api.request("/api/ejemplar/disponibilidad")
        books = app.api.request("/api/libro")
        states = app.api.request("/api/estado/prestamo")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    if not members or not branches or not ejemplares:
        notify(
            app.page,
            "Se necesita al menos un socio habilitado, una sede activa y "
            "un ejemplar disponible.",
            True,
        )
        return

    member_options = [
        ft.dropdown.Option(
            str(item["id"]), f"{item['apellido']}, {item['nombre']} · {item['dni']}"
        )
        for item in members
    ]
    branch_options = [
        ft.dropdown.Option(str(item["id"]), item["nombre"]) for item in branches
    ]
    book_names = {book["id"]: book["titulo"] for book in books}
    copy_options = [
        ft.dropdown.Option(
            str(item["id"]),
            f"{item['codigo']} · {book_names.get(item['libro_id'], 'Libro sin título')}",
        )
        for item in ejemplares
    ]
    initial_state = next(
        (state for state in states if state["descripcion"].casefold() == "pendiente"),
        None,
    )
    if initial_state is None:
        notify(
            app.page, "No se encontró el estado inicial 'Pendiente' en la API.", True
        )
        return

    member = ft.Dropdown(label="Socio", options=member_options, border_radius=10)
    branch = ft.Dropdown(label="Sede de retiro", options=branch_options, border_radius=10)
    copy = ft.Dropdown(label="Ejemplar disponible", options=copy_options, border_radius=10)
    start = text_input("Fecha de inicio", value=date.today().isoformat())
    due = text_input(
        "Fecha de vencimiento",
        value=(date.today() + timedelta(days=14)).isoformat(),
    )

    def submit() -> None:
        if not all(control.value for control in (member, branch, copy)):
            notify(app.page, "Seleccioná socio, sede y ejemplar.", True)
            return
        try:
            start_date = date.fromisoformat(start.value)
            due_date = date.fromisoformat(due.value)
            if due_date < start_date:
                notify(
                    app.page, "El vencimiento no puede ser anterior al inicio.", True
                )
                return
            app.api.request(
                "/api/prestamo-local",
                "POST",
                {
                    "fecha_inicio": start_date.isoformat(),
                    "fecha_vencimiento": due_date.isoformat(),
                    "fecha_devolucion": None,
                    "estado_prestamo_id": initial_state["id"],
                    "ejemplar_id": int(copy.value),
                    "multa_id": None,
                    "devolucion_id": None,
                    "sede_origen_id": int(branch.value),
                    "socio_id": int(member.value),
                },
            )
        except ValueError:
            notify(app.page, "Usá fechas válidas con formato AAAA-MM-DD.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Préstamo creado correctamente.")
        app.navigate("Préstamos")

    open_form(
        app.page,
        "Crear préstamo local",
        [member, branch, copy, start, due],
        submit,
    )


def _return_prestamo(app: LibraryApp, prestamo: dict[str, Any]) -> None:
    condition = ft.Dropdown(
        label="Estado físico",
        value="Bueno",
        options=[
            ft.dropdown.Option(value, value)
            for value in ("Bueno", "Regular", "Dañado", "Extraviado", "Destruido")
        ],
        border_radius=10,
    )
    notes = text_input(
        "Observaciones (opcional)", multiline=True, min_lines=2, max_lines=4
    )

    def submit() -> None:
        try:
            app.api.request(
                f"/api/devolucion/prestamo/{prestamo['id']}",
                "POST",
                {
                    "fecha": date.today().isoformat(),
                    "observaciones": notes.value.strip() or None,
                    "estado_fisico": condition.value,
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Devolución registrada.")
        app.navigate("Préstamos")

    open_form(
        app.page,
        f"Devolución del préstamo #{prestamo['id']}",
        [condition, notes],
        submit,
    )
