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
    socios = app.api.request("/api/socio")
    search = text_input("Buscar por nombre, DNI o email", prefix_icon=ft.Icons.SEARCH)
    table = ft.Container()

    def render_rows(_: Any = None) -> None:
        term = search.value.strip().casefold()
        filtered = [
            socio
            for socio in socios
            if term
            in (
                f"{socio['nombre']} {socio['apellido']} "
                f"{socio['dni']} {socio['email']}"
            ).casefold()
        ]
        table.content = data_table(
            ["Socio", "DNI", "Email", "Teléfono", "Estado", "Acciones"],
            [
                [
                    ft.Text(
                        f"{socio['nombre']} {socio['apellido']}",
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(str(socio["dni"])),
                    ft.Text(socio["email"]),
                    ft.Text(socio["telefono"]),
                    ft.Text(
                        "Habilitado" if socio["habilitado"] else "Deshabilitado"
                    ),
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip="Editar socio",
                                on_click=lambda _, selected=socio: _edit_socio(
                                    app, selected
                                ),
                            ),
                            *(
                                [
                                    ft.TextButton(
                                        "Deshabilitar",
                                        icon=ft.Icons.BLOCK,
                                        on_click=lambda _, selected=socio: (
                                            _confirm_disable_socio(app, selected)
                                        ),
                                    )
                                ]
                                if socio["habilitado"]
                                else []
                            ),
                        ],
                        spacing=0,
                    ),
                ]
                for socio in filtered
            ],
        )
        app.page.update()

    search.on_change = render_rows
    view = ft.Column(
        [
            section_header(
                "Socios",
                "Consultá y registrá a los miembros de la biblioteca.",
                "Nuevo socio",
                lambda _: _new_socio(app),
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


def _confirm_disable_socio(app: LibraryApp, socio: dict[str, Any]) -> None:
    def disable(_: Any) -> None:
        try:
            app.api.request(f"/api/socio/{socio['id']}", "DELETE")
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Socio deshabilitado correctamente.")
        app.navigate("Socios")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Deshabilitar socio"),
        content=ft.Text(
            f"¿Querés deshabilitar a {socio['nombre']} {socio['apellido']}? "
            "El socio no se eliminará permanentemente."
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton("Deshabilitar socio", on_click=disable),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _new_socio(app: LibraryApp) -> None:
    name = text_input("Nombre")
    surname = text_input("Apellido")
    dni = text_input("DNI", keyboard_type=ft.KeyboardType.NUMBER)
    email = text_input("Email", keyboard_type=ft.KeyboardType.EMAIL)
    phone = text_input("Teléfono", keyboard_type=ft.KeyboardType.PHONE)

    def submit() -> None:
        if not all(
            field.value.strip() for field in (name, surname, dni, email, phone)
        ):
            notify(app.page, "Completá todos los campos.", True)
            return
        try:
            app.api.request(
                "/api/socio",
                "POST",
                {
                    "nombre": name.value.strip(),
                    "apellido": surname.value.strip(),
                    "dni": int(dni.value),
                    "email": email.value.strip(),
                    "telefono": phone.value.strip(),
                    "habilitado": True,
                },
            )
        except ValueError:
            notify(app.page, "El DNI debe ser un número.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Socio registrado correctamente.")
        app.navigate("Socios")

    open_form(
        app.page,
        "Registrar socio",
        [name, surname, dni, email, phone],
        submit,
    )


def _edit_socio(app: LibraryApp, socio: dict[str, Any]) -> None:
    name = text_input("Nombre", value=socio["nombre"])
    surname = text_input("Apellido", value=socio["apellido"])
    dni = text_input(
        "DNI", value=str(socio["dni"]), keyboard_type=ft.KeyboardType.NUMBER
    )
    email = text_input(
        "Email", value=socio["email"], keyboard_type=ft.KeyboardType.EMAIL
    )
    phone = text_input(
        "Teléfono", value=socio["telefono"], keyboard_type=ft.KeyboardType.PHONE
    )
    enabled = ft.Switch(label="Socio habilitado", value=socio["habilitado"])

    def submit() -> None:
        if not all(field.value.strip() for field in (name, surname, dni, email, phone)):
            notify(app.page, "Completá todos los campos.", True)
            return
        try:
            app.api.request(
                f"/api/socio/{socio['id']}",
                "PUT",
                {
                    "nombre": name.value.strip(),
                    "apellido": surname.value.strip(),
                    "dni": int(dni.value),
                    "email": email.value.strip(),
                    "telefono": phone.value.strip(),
                    "habilitado": enabled.value,
                },
            )
        except ValueError:
            notify(app.page, "El DNI debe ser un número.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Socio actualizado correctamente.")
        app.navigate("Socios")

    open_form(
        app.page,
        f"Editar socio #{socio['id']}",
        [name, surname, dni, email, phone, enabled],
        submit,
    )
