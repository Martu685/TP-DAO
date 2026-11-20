from __future__ import annotations

from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.api.client import ApiError
from frontend.ui import theme
from frontend.ui.components import (
    card,
    notify,
    text_input,
    update_form_errors,
)

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build_login(app: LibraryApp, email: str = "") -> ft.Control:
    email_field = text_input(
        "Email",
        value=email,
        keyboard_type=ft.KeyboardType.EMAIL,
        autofocus=True,
    )
    password_field = text_input(
        "Contraseña",
        password=True,
        can_reveal_password=True,
        on_submit=lambda _: login(),
    )

    def login(_: Any = None) -> None:
        fields = [email_field, password_field]
        errors = []
        if not email_field.value.strip():
            errors.append((email_field, "Ingresá tu email."))
        if not password_field.value:
            errors.append((password_field, "Ingresá tu contraseña."))
        if update_form_errors(app.page, fields, errors):
            return
        try:
            response = app.api.request(
                "/api/usuario/login",
                "POST",
                {
                    "email": email_field.value.strip(),
                    "password": password_field.value,
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        app.api.access_token = response["access_token"]
        app.current_user = response["usuario"]
        password_field.value = ""
        app.show_authenticated_app()

    return _auth_layout(
        ft.Column(
            [
                ft.Text(
                    "Iniciar sesión",
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    color=theme.INK,
                ),
                ft.Text(
                    "Ingresá a la gestión de la biblioteca.",
                    color=theme.MUTED,
                ),
                email_field,
                password_field,
                ft.FilledButton(
                    "Iniciar sesión",
                    icon=ft.Icons.LOGIN,
                    on_click=login,
                ),
                ft.TextButton(
                    "¿No tenés cuenta? Registrate",
                    on_click=lambda _: app.show_registration(),
                ),
            ],
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )


def build_registration(app: LibraryApp) -> ft.Control:
    name = text_input("Nombre")
    surname = text_input("Apellido")
    dni = text_input("DNI", keyboard_type=ft.KeyboardType.NUMBER)
    email = text_input("Email", keyboard_type=ft.KeyboardType.EMAIL)
    phone = text_input("Teléfono", keyboard_type=ft.KeyboardType.PHONE)
    password = text_input(
        "Contraseña",
        password=True,
        can_reveal_password=True,
    )

    def register(_: Any = None) -> None:
        fields = [name, surname, dni, email, phone, password]
        errors = [
            (field, "Completá este campo.")
            for field in fields
            if not field.value.strip()
        ]
        if update_form_errors(app.page, fields, errors):
            return
        try:
            dni_value = int(dni.value.strip())
        except ValueError:
            update_form_errors(
                app.page, fields, [(dni, "El DNI debe ser un número entero.")]
            )
            return
        if not 8 <= len(password.value) <= 128:
            update_form_errors(
                app.page,
                fields,
                [(password, "Usá entre 8 y 128 caracteres.")],
            )
            return

        try:
            created_user = app.api.request(
                "/api/usuario/registro",
                "POST",
                {
                    "nombre": name.value.strip(),
                    "apellido": surname.value.strip(),
                    "dni": dni_value,
                    "email": email.value.strip(),
                    "telefono": phone.value.strip(),
                    "password": password.value,
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        app.show_login(created_user["email"])
        notify(
            app.page,
            "Cuenta de socio creada. Ahora podés iniciar sesión.",
        )

    return _auth_layout(
        ft.Column(
            [
                ft.Text(
                    "Crear cuenta",
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    color=theme.INK,
                ),
                ft.Text(
                    "Registrate como socio de la biblioteca.",
                    color=theme.MUTED,
                ),
                name,
                surname,
                dni,
                email,
                phone,
                password,
                ft.FilledButton(
                    "Registrarme",
                    icon=ft.Icons.PERSON_ADD_ALT_1,
                    on_click=register,
                ),
                ft.TextButton(
                    "Ya tengo una cuenta",
                    on_click=lambda _: app.show_login(email.value.strip()),
                ),
            ],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )


def _auth_layout(form: ft.Control) -> ft.Container:
    auth_card = card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.AUTO_STORIES,
                            color=theme.ACCENT,
                            size=28,
                        ),
                        ft.Text(
                            "Biblioteca UTN",
                            size=19,
                            weight=ft.FontWeight.W_600,
                            color=theme.INK,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                form,
            ],
            spacing=24,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            width=float("inf"),
        ),
        padding=28,
    )
    auth_card.width = 460
    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=auth_card,
                    width=460,
                    alignment=ft.Alignment(0, 0),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            width=float("inf"),
            scroll=ft.ScrollMode.AUTO,
        ),
        expand=True,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
    )
