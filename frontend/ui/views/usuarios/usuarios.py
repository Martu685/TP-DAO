from __future__ import annotations

from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.api.client import ApiError
from frontend.ui.components import card, empty_state, notify, section_header, text_input

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    if not app.current_user or app.current_user.get("rol") != "admin":
        return empty_state(
            "Solo un administrador puede crear cuentas del equipo.",
            ft.Icons.LOCK_OUTLINE,
        )

    try:
        branches = [
            branch
            for branch in app.api.request("/api/sede")
            if branch.get("activa")
        ]
    except ApiError as error:
        return empty_state(f"No se pudieron cargar las sedes: {error}", ft.Icons.CLOUD_OFF_OUTLINED)

    email = text_input("Email del nuevo usuario", keyboard_type=ft.KeyboardType.EMAIL)
    password = text_input(
        "Contraseña",
        password=True,
        can_reveal_password=True,
    )
    role = ft.Dropdown(
        label="Rol",
        value="bibliotecario",
        options=[
            ft.dropdown.Option("bibliotecario", "Bibliotecario"),
            ft.dropdown.Option("admin", "Administrador"),
        ],
        border_radius=10,
    )
    branch = ft.Dropdown(
        label="Sede asignada (opcional)",
        options=[
            ft.dropdown.Option(str(item["id"]), item["nombre"])
            for item in branches
        ],
        border_radius=10,
    )

    def create_staff(_: Any = None) -> None:
        if not email.value.strip() or not password.value:
            notify(app.page, "Completá el email y la contraseña.", True)
            return
        if not 8 <= len(password.value) <= 128:
            notify(app.page, "La contraseña debe tener entre 8 y 128 caracteres.", True)
            return
        if role.value not in {"bibliotecario", "admin"}:
            notify(app.page, "Seleccioná un rol válido para la cuenta.", True)
            return

        try:
            created_user = app.api.request(
                "/api/usuario/equipo",
                "POST",
                {
                    "email": email.value.strip(),
                    "password": password.value,
                    "rol": role.value,
                    "sede_id": int(branch.value) if branch.value else None,
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        password.value = ""
        notify(
            app.page,
            f"Cuenta de {created_user['rol']} creada para {created_user['email']}.",
        )
        app.page.update()

    return ft.Column(
        [
            section_header(
                "Cuentas del equipo",
                "Registrá usuarios bibliotecarios o administradores.",
            ),
            card(
                ft.Column(
                    [
                        email,
                        password,
                        role,
                        branch,
                        ft.FilledButton(
                            "Crear cuenta",
                            icon=ft.Icons.PERSON_ADD_ALT_1,
                            on_click=create_staff,
                        ),
                    ],
                    spacing=14,
                ),
                padding=24,
            ),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
