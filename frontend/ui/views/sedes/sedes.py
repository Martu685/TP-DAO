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
    sedes = app.api.request("/api/sede")
    search = text_input(
        "Buscar por nombre, dirección o email", prefix_icon=ft.Icons.SEARCH
    )
    table = ft.Container()

    def render_rows(_: Any = None) -> None:
        term = search.value.strip().casefold()
        filtered = [
            sede
            for sede in sedes
            if term
            in (
                f"{sede['nombre']} {sede['direccion']} "
                f"{sede['email']} {sede['horarios']}"
            ).casefold()
        ]
        table.content = data_table(
            ["Sede", "Dirección", "Email", "Horarios", "Estado", "Acciones"],
            [
                [
                    ft.Text(sede["nombre"], weight=ft.FontWeight.W_500),
                    ft.Text(sede["direccion"]),
                    ft.Text(sede["email"]),
                    ft.Text(sede["horarios"]),
                    ft.Text("Activa" if sede["activa"] else "Inactiva"),
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip="Editar sede",
                                on_click=lambda _, selected=sede: _edit_sede(
                                    app, selected
                                ),
                            ),
                            *(
                                [
                                    ft.TextButton(
                                        "Desactivar",
                                        icon=ft.Icons.BLOCK,
                                        on_click=lambda _, selected=sede: (
                                            _confirm_deactivate_sede(app, selected)
                                        ),
                                    )
                                ]
                                if sede["activa"]
                                else []
                            ),
                        ],
                        spacing=0,
                    ),
                ]
                for sede in filtered
            ],
        )
        app.page.update()

    search.on_change = render_rows
    view = ft.Column(
        [
            section_header(
                "Sedes",
                "Administrá las sedes y sus datos de atención.",
                "Nueva sede",
                lambda _: _new_sede(app),
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


def _confirm_deactivate_sede(app: LibraryApp, sede: dict[str, Any]) -> None:
    def deactivate(_: Any) -> None:
        try:
            app.api.request(f"/api/sede/{sede['id']}", "DELETE")
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Sede desactivada correctamente.")
        app.navigate("Sedes")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Desactivar sede"),
        content=ft.Text(
            f"¿Querés desactivar la sede {sede['nombre']}? "
            "La sede no se eliminará permanentemente."
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton("Desactivar sede", on_click=deactivate),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _new_sede(app: LibraryApp) -> None:
    name = text_input("Nombre")
    address = text_input("Dirección")
    email = text_input("Email", keyboard_type=ft.KeyboardType.EMAIL)
    hours = text_input("Horarios", hint_text="Ej.: Lunes a viernes, 9 a 18 h")

    def submit() -> None:
        fields = [name, address, email, hours]
        errors = [
            (field, "Completá este campo.")
            for field in fields
            if not field.value.strip()
        ]
        if update_form_errors(app.page, fields, errors):
            return
        try:
            app.api.request(
                "/api/sede",
                "POST",
                {
                    "nombre": name.value.strip(),
                    "direccion": address.value.strip(),
                    "email": email.value.strip(),
                    "horarios": hours.value.strip(),
                    "activa": True,
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Sede registrada correctamente.")
        app.navigate("Sedes")

    open_form(app.page, "Registrar sede", [name, address, email, hours], submit)


def _edit_sede(app: LibraryApp, sede: dict[str, Any]) -> None:
    name = text_input("Nombre", value=sede["nombre"])
    address = text_input("Dirección", value=sede["direccion"])
    email = text_input(
        "Email", value=sede["email"], keyboard_type=ft.KeyboardType.EMAIL
    )
    hours = text_input("Horarios", value=sede["horarios"])
    active = ft.Switch(label="Sede activa", value=sede["activa"])

    def save() -> bool:
        fields = [name, address, email, hours]
        errors = [
            (field, "Completá este campo.")
            for field in fields
            if not field.value.strip()
        ]
        if update_form_errors(app.page, fields, errors):
            return False
        try:
            app.api.request(
                f"/api/sede/{sede['id']}",
                "PUT",
                {
                    "nombre": name.value.strip(),
                    "direccion": address.value.strip(),
                    "email": email.value.strip(),
                    "horarios": hours.value.strip(),
                    "activa": active.value,
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return False
        return True

    def submit() -> None:
        if sede["activa"] and not active.value:
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Desactivar sede"),
                content=ft.Text(
                    f"¿Querés desactivar la sede {name.value.strip()}? "
                    "La sede no se eliminará permanentemente."
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
                    ft.FilledButton(
                        "Desactivar sede",
                        on_click=confirm_deactivation,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            app.page.show_dialog(dialog)
            return
        if save():
            app.page.pop_dialog()
            notify(app.page, "Sede actualizada correctamente.")
            app.navigate("Sedes")

    def confirm_deactivation(_: Any) -> None:
        if save():
            app.page.pop_dialog()
            app.page.pop_dialog()
            notify(app.page, "Sede actualizada correctamente.")
            app.navigate("Sedes")

    open_form(
        app.page,
        f"Editar sede #{sede['id']}",
        [name, address, email, hours, active],
        submit,
    )
