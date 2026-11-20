from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.api.client import ApiError
from frontend.ui import theme
from frontend.ui.components import (
    card,
    data_table,
    empty_state,
    notify,
    open_form,
    section_header,
    text_input,
    update_form_errors,
)

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    is_member = bool(app.current_user and app.current_user["rol"] == "socio")
    reservations = app.api.request("/api/reserva")
    states = app.api.request("/api/estado/reserva")
    members = [] if is_member else app.api.request("/api/socio")
    copies = app.api.request("/api/ejemplar")
    branches = app.api.request("/api/sede")
    books = app.api.request("/api/libro")

    state_names = {state["id"]: state["descripcion"] for state in states}
    member_names = {
        member["id"]: f"{member['nombre']} {member['apellido']}"
        for member in members
    }
    branch_names = {branch["id"]: branch["nombre"] for branch in branches}
    copy_names = {
        copy["id"]: {
            "codigo": copy["codigo"],
            "libro_id": copy["libro_id"],
        }
        for copy in copies
    }
    book_names = {book["id"]: book["titulo"] for book in books}

    search = text_input(
        "Buscar por ejemplar o estado"
        if is_member
        else "Buscar por socio, ejemplar o estado",
        prefix_icon=ft.Icons.SEARCH,
    )
    table = ft.Container()

    def render_rows(_: Any = None) -> None:
        term = search.value.strip().casefold()
        filtered = []
        for reservation in reservations:
            copy = copy_names.get(reservation["ejemplar_id"], {})
            state_name = state_names.get(
                reservation["estado_reserva_id"], "Desconocido"
            )
            searchable = " ".join(
                [
                    ""
                    if is_member
                    else member_names.get(reservation["socio_id"], ""),
                    copy.get("codigo", ""),
                    book_names.get(copy.get("libro_id"), ""),
                    branch_names.get(reservation["sede_id"], ""),
                    state_name,
                ]
            )
            if term in searchable.casefold():
                row = [
                    ft.Text(f"#{reservation['id']}", weight=ft.FontWeight.W_500),
                    ft.Text(reservation["fecha"]),
                ]
                if not is_member:
                    row.append(
                        ft.Text(
                            member_names.get(
                                reservation["socio_id"],
                                f"Socio #{reservation['socio_id']}",
                            )
                        ),
                    )
                row.extend(
                    [
                        ft.Text(
                            f"{copy.get('codigo', '—')} · "
                            f"{book_names.get(copy.get('libro_id'), 'Libro')}",
                        ),
                        ft.Text(
                            branch_names.get(
                                reservation["sede_id"],
                                f"Sede #{reservation['sede_id']}",
                            )
                        ),
                        ft.Text(state_name),
                    ]
                )
                if not is_member:
                    row.append(
                        ft.Row(
                            _reservation_actions(
                                app,
                                reservation,
                                state_name,
                            ),
                            spacing=4,
                            wrap=True,
                        )
                    )
                filtered.append(row)

        headers = ["N.º", "Fecha"]
        if not is_member:
            headers.append("Socio")
        headers.extend(["Ejemplar", "Sede", "Estado"])
        if not is_member:
            headers.append("Acciones")
        table.content = (
            empty_state(
                "Todavía no tenés reservas registradas.",
                ft.Icons.BOOKMARK_OUTLINED,
            )
            if is_member and not filtered
            else data_table(headers, filtered)
        )
        app.page.update()

    search.on_change = render_rows
    render_rows()

    return ft.Column(
        [
            section_header(
                "Mis reservas" if is_member else "Reservas",
                "Consultá tus reservas y sus estados."
                if is_member
                else "Administrá reservas y su transición de estado.",
                None if is_member else "Nueva reserva",
                None if is_member else lambda _: _new_reservation(app),
            ),
            card(search, 12),
            card(table, 8),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _reservation_actions(
    app: LibraryApp,
    reservation: dict[str, Any],
    state_name: str,
) -> list[ft.Control]:
    actions: list[ft.Control] = [
        ft.IconButton(
            icon=ft.Icons.VISIBILITY_OUTLINED,
            tooltip="Ver detalle",
            on_click=lambda _, selected=reservation: _show_reservation(
                app,
                selected,
            ),
        )
    ]
    normalized = state_name.casefold()
    if normalized == "pendiente":
        actions.extend(
            [
                ft.TextButton(
                    "Aceptar",
                    on_click=lambda _, selected=reservation: _change_state(
                        app,
                        selected,
                        "Aceptada",
                        "Reserva aceptada.",
                    ),
                ),
                ft.TextButton(
                    "Rechazar",
                    on_click=lambda _, selected=reservation: _change_state(
                        app,
                        selected,
                        "Rechazada",
                        "Reserva rechazada.",
                    ),
                ),
            ]
        )
    elif normalized == "aceptada":
        actions.append(
            ft.TextButton(
                "Cancelar",
                on_click=lambda _, selected=reservation: _confirm_delete_reservation(
                    app,
                    selected,
                ),
            )
        )
    return actions


def _show_reservation(
    app: LibraryApp,
    reservation: dict[str, Any],
) -> None:
    try:
        selected = app.api.request(f"/api/reserva/{reservation['id']}")
        states = app.api.request("/api/estado/reserva")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    state_name = next(
        (
            state["descripcion"]
            for state in states
            if state["id"] == selected["estado_reserva_id"]
        ),
        "Desconocido",
    )
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Reserva #{selected['id']}"),
        content=ft.Column(
            [
                ft.Text(f"Fecha: {selected['fecha']}"),
                ft.Text(f"Socio: #{selected['socio_id']}"),
                ft.Text(f"Ejemplar: #{selected['ejemplar_id']}"),
                ft.Text(f"Sede: #{selected['sede_id']}"),
                ft.Text(f"Estado: {state_name}", weight=ft.FontWeight.W_600),
            ],
            tight=True,
            spacing=10,
        ),
        actions=[
            ft.TextButton("Cerrar", on_click=lambda _: app.page.pop_dialog())
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _new_reservation(app: LibraryApp) -> None:
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
        copies = app.api.request("/api/ejemplar")
        books = app.api.request("/api/libro")
        states = app.api.request("/api/estado/reserva")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    pending = next(
        (
            state
            for state in states
            if state["descripcion"].casefold() == "pendiente"
        ),
        None,
    )
    if pending is None:
        notify(app.page, "No se encontró el estado Pendiente.", True)
        return
    if not members or not branches or not copies:
        notify(
            app.page,
            "Se necesitan socios, sedes y ejemplares registrados.",
            True,
        )
        return

    book_names = {book["id"]: book["titulo"] for book in books}
    member = ft.Dropdown(
        label="Socio",
        options=[
            ft.dropdown.Option(
                str(item["id"]),
                f"{item['apellido']}, {item['nombre']} · {item['dni']}",
            )
            for item in members
        ],
        border_radius=10,
    )
    branch = ft.Dropdown(
        label="Sede",
        options=[
            ft.dropdown.Option(str(item["id"]), item["nombre"])
            for item in branches
        ],
        border_radius=10,
    )
    copy = ft.Dropdown(
        label="Ejemplar",
        options=[
            ft.dropdown.Option(
                str(item["id"]),
                f"{item['codigo']} · "
                f"{book_names.get(item['libro_id'], 'Libro sin título')}",
            )
            for item in copies
        ],
        border_radius=10,
    )
    reservation_date = text_input(
        "Fecha de reserva",
        value=date.today().isoformat(),
    )

    def submit() -> None:
        fields = [reservation_date, member, branch, copy]
        errors = [
            (field, "Seleccioná una opción.")
            for field in (member, branch, copy)
            if not field.value
        ]
        if update_form_errors(app.page, fields, errors):
            return
        try:
            parsed_date = date.fromisoformat(reservation_date.value.strip())
        except ValueError:
            update_form_errors(
                app.page,
                fields,
                [(reservation_date, "Usá el formato AAAA-MM-DD.")],
            )
            return
        try:
            app.api.request(
                "/api/reserva",
                "POST",
                {
                    "fecha": parsed_date.isoformat(),
                    "estado_reserva_id": pending["id"],
                    "socio_id": int(member.value),
                    "ejemplar_id": int(copy.value),
                    "sede_id": int(branch.value),
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Reserva creada correctamente.")
        app.navigate("Reservas")

    open_form(
        app.page,
        "Nueva reserva",
        [reservation_date, member, branch, copy],
        submit,
    )


def _change_state(
    app: LibraryApp,
    reservation: dict[str, Any],
    target_state_name: str,
    success_message: str,
) -> None:
    def confirm(_: Any) -> None:
        try:
            states = app.api.request("/api/estado/reserva")
            target = next(
                state
                for state in states
                if state["descripcion"].casefold()
                == target_state_name.casefold()
            )
            app.api.request(
                f"/api/reserva/{reservation['id']}",
                "PUT",
                {
                    "fecha": reservation["fecha"],
                    "estado_reserva_id": target["id"],
                    "socio_id": reservation["socio_id"],
                    "ejemplar_id": reservation["ejemplar_id"],
                    "sede_id": reservation["sede_id"],
                },
            )
        except StopIteration:
            notify(
                app.page,
                f"No se encontró el estado {target_state_name}.",
                True,
            )
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, success_message)
        app.navigate("Reservas")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"{target_state_name} reserva"),
        content=ft.Text(
            f"¿Querés cambiar la reserva #{reservation['id']} "
            f"a {target_state_name}?"
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton(target_state_name, on_click=confirm),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _confirm_delete_reservation(
    app: LibraryApp,
    reservation: dict[str, Any],
) -> None:
    def delete(_: Any) -> None:
        try:
            app.api.request(
                f"/api/reserva/{reservation['id']}",
                "DELETE",
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Reserva cancelada.")
        app.navigate("Reservas")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Cancelar reserva"),
        content=ft.Text(
            f"¿Querés cancelar la reserva #{reservation['id']}?"
        ),
        actions=[
            ft.TextButton("No", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton("Cancelar reserva", on_click=delete),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)
