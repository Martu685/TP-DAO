from collections.abc import Callable

import flet as ft

from frontend.api.client import ApiClient, ApiError
from frontend.ui import theme
from frontend.ui.components import empty_state, notify, text_input
from frontend.ui.views.inicio import (
    dashboard,
)
from frontend.ui.views.ejemplares import ejemplares
from frontend.ui.views.historial import historial
from frontend.ui.views.libros import libros
from frontend.ui.views.prestamos import prestamos
from frontend.ui.views.reportes import reportes
from frontend.ui.views.remitos import remitos
from frontend.ui.views.sedes import sedes
from frontend.ui.views.socios import socios


NAV_ITEMS = (
    ("Inicio", ft.Icons.DASHBOARD_OUTLINED),
    ("Libros", ft.Icons.MENU_BOOK_OUTLINED),
    ("Socios", ft.Icons.GROUP_OUTLINED),
    ("Historial de lecturas", ft.Icons.HISTORY_OUTLINED),
    ("Sedes", ft.Icons.LOCATION_ON_OUTLINED),
    ("Ejemplares", ft.Icons.INVENTORY_2_OUTLINED),
    ("Remitos", ft.Icons.LOCAL_SHIPPING_OUTLINED),
    ("Préstamos", ft.Icons.SWAP_HORIZ_OUTLINED),
    ("Reportes", ft.Icons.ANALYTICS_OUTLINED),
)


class LibraryApp:
    def __init__(self, page: ft.Page, api: ApiClient) -> None:
        self.page = page
        self.api = api
        self.current_user: dict[str, object] | None = None
        self.content = ft.Container(expand=True, padding=32)
        self.selected_label = ft.Text(
            "Biblioteca UTN",
            size=18,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.WHITE,
        )
        self.nav_column = ft.Column(spacing=6)

    def run(self) -> None:
        self.page.title = "Biblioteca UTN | Gestión"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.theme = ft.Theme(color_scheme_seed=theme.ACCENT)
        self.page.bgcolor = theme.BACKGROUND
        self.page.padding = 0
        self.page.window_min_width = 900
        self.page.window_min_height = 620
        self._build_navigation()

        sidebar = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.AUTO_STORIES,
                                color=ft.Colors.WHITE,
                                size=22,
                            ),
                            self.selected_label,
                        ],
                        spacing=11,
                    ),
                    ft.Container(height=24),
                    ft.Text(
                        "MENÚ", size=10, color="#A6B8AE", weight=ft.FontWeight.BOLD
                    ),
                    self.nav_column,
                    ft.Container(expand=True),
                    ft.Divider(color="#3B5147"),
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CLOUD_DONE_OUTLINED,
                                color="#A6B8AE",
                                size=16,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        "API configurada",
                                        size=10,
                                        color="#A6B8AE",
                                    ),
                                    ft.Text(
                                        self.api.base_url,
                                        size=10,
                                        color="#E1E9E4",
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=9,
                    ),
                ],
                spacing=10,
                expand=True,
            ),
            width=235,
            bgcolor=theme.SIDEBAR,
            padding=22,
        )
        self.page.add(
            ft.Row(
                [
                    sidebar,
                    ft.VerticalDivider(width=1, color=theme.BORDER),
                    self.content,
                ],
                expand=True,
                spacing=0,
            )
        )
        self._show_login_dialog()

    def _show_login_dialog(self) -> None:
        email = text_input(
            "Email",
            keyboard_type=ft.KeyboardType.EMAIL,
            prefix_icon=ft.Icons.EMAIL_OUTLINED,
        )
        password = text_input(
            "Contraseña",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_OUTLINED,
        )

        def submit() -> None:
            if not email.value.strip() or not password.value:
                notify(self.page, "Completá email y contraseña.", True)
                return
            try:
                response = self.api.request(
                    "/api/usuario/login",
                    "POST",
                    {
                        "email": email.value.strip(),
                        "password": password.value,
                    },
                )
            except ApiError as error:
                notify(self.page, str(error), True)
                return

            user = response["usuario"]
            if user["rol"] not in {"bibliotecario", "admin"}:
                notify(
                    self.page,
                    "Esta interfaz requiere una cuenta de bibliotecario o administrador.",
                    True,
                )
                return

            self.api.set_access_token(response["access_token"])
            self.current_user = user
            self.page.pop_dialog()
            notify(
                self.page,
                f"Bienvenido, {user['email']}.",
            )
            self.navigate("Inicio")

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Iniciar sesión", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Ingresá con una cuenta de bibliotecario o administrador.",
                            color=theme.MUTED,
                        ),
                        email,
                        password,
                    ],
                    tight=True,
                    spacing=14,
                ),
                width=420,
            ),
            actions=[
                ft.FilledButton(
                    "Ingresar",
                    icon=ft.Icons.LOGIN,
                    on_click=lambda _: submit(),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)

    def navigate(self, section: str) -> None:
        self.selected_label.value = "Biblioteca UTN" if section == "Inicio" else section
        for button, (label, _) in zip(self.nav_column.controls, NAV_ITEMS):
            button.bgcolor = theme.ACCENT if label == section else None
        try:
            self.content.content = self._view_for(section)()
        except ApiError as error:
            self.content.content = empty_state(
                str(error), ft.Icons.CLOUD_OFF_OUTLINED
            )
        self.page.update()

    def _view_for(self, section: str) -> Callable[[], ft.Control]:
        views: dict[str, Callable[[], ft.Control]] = {
            "Inicio": lambda: dashboard.build(self),
            "Libros": lambda: libros.build(self),
            "Socios": lambda: socios.build(self),
            "Historial de lecturas": lambda: historial.build(self),
            "Sedes": lambda: sedes.build(self),
            "Ejemplares": lambda: ejemplares.build(self),
            "Remitos": lambda: remitos.build(self),
            "Préstamos": lambda: prestamos.build(self),
            "Reportes": lambda: reportes.build(self),
        }
        return views[section]

    def _build_navigation(self) -> None:
        for label, icon in NAV_ITEMS:
            self.nav_column.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(icon, size=19, color="#E4ECE6"),
                            ft.Text(
                                label,
                                color="#F1F5F2",
                                size=14,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        spacing=13,
                    ),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    border_radius=10,
                    on_click=lambda _, section=label: self.navigate(section),
                )
            )
