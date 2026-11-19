from collections.abc import Callable
from typing import Any

import flet as ft

from frontend.api.client import ApiClient, ApiError
from frontend.ui import theme
from frontend.ui.components import empty_state, notify, text_input
from frontend.ui.views.inicio import (
    dashboard,
)
from frontend.ui.views import notificaciones
from frontend.ui.views.ejemplares import ejemplares
from frontend.ui.views.historial import historial
from frontend.ui.views.libros import libros
from frontend.ui.views.prestamos import mis_prestamos
from frontend.ui.views.prestamos import prestamos
from frontend.ui.views.reportes import reportes
from frontend.ui.views.remitos import remitos
from frontend.ui.views.reservas import reservas
from frontend.ui.views.sedes import sedes
from frontend.ui.views.socios import socios
from frontend.ui.views.usuarios import acceso, usuarios


NAV_ITEMS = (
    ("Inicio", ft.Icons.DASHBOARD_OUTLINED),
    ("Libros", ft.Icons.MENU_BOOK_OUTLINED),
    ("Socios", ft.Icons.GROUP_OUTLINED),
    ("Usuarios", ft.Icons.PERSON_OUTLINED),
    ("Historial de lecturas", ft.Icons.HISTORY_OUTLINED),
    ("Sedes", ft.Icons.LOCATION_ON_OUTLINED),
    ("Ejemplares", ft.Icons.INVENTORY_2_OUTLINED),
    ("Remitos", ft.Icons.LOCAL_SHIPPING_OUTLINED),
    ("Reservas", ft.Icons.BOOKMARK_OUTLINED),
    ("Préstamos", ft.Icons.SWAP_HORIZ_OUTLINED),
    ("Reportes", ft.Icons.ANALYTICS_OUTLINED),
    ("Notificaciones", ft.Icons.NOTIFICATIONS_OUTLINED),
)


class LibraryApp:
    def __init__(self, page: ft.Page, api: ApiClient) -> None:
        self.page = page
        self.api = api
        self.current_user: dict[str, Any] | None = None
        self.root = ft.Container(expand=True)
        self.content = ft.Container(expand=True, padding=32)
        self.selected_label = ft.Text(
            "Biblioteca UTN",
            size=18,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.WHITE,
        )
        self.nav_column = ft.Column(
            spacing=6,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def run(self) -> None:
        self.page.title = "Biblioteca UTN | Gestión"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.theme = ft.Theme(color_scheme_seed=theme.ACCENT)
        self.page.bgcolor = theme.BACKGROUND
        self.page.padding = 0
        self.page.window_min_width = 900
        self.page.window_min_height = 620
        self.page.add(self.root)
        self.show_login()

    def show_login(self, email: str = "") -> None:
        self.root.content = acceso.build_login(self, email)
        self.page.update()

    def show_registration(self) -> None:
        self.root.content = acceso.build_registration(self)
        self.page.update()

    def show_authenticated_app(self) -> None:
        if self.current_user is None:
            self.show_login()
            return

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
                    ft.Divider(color="#3B5147"),
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.PERSON_OUTLINED,
                                color="#A6B8AE",
                                size=16,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        self.current_user["email"],
                                        size=10,
                                        color="#E1E9E4",
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        self.current_user["rol"].capitalize(),
                                        size=10,
                                        color="#A6B8AE",
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=9,
                    ),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.LOGOUT,
                                    color="#E4ECE6",
                                    size=18,
                                ),
                                ft.Text(
                                    "Cerrar sesión",
                                    color="#F1F5F2",
                                    size=14,
                                ),
                            ],
                            spacing=13,
                        ),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                        border_radius=10,
                        on_click=lambda _: self.logout(),
                    ),
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
        self.root.content = ft.Row(
            [
                sidebar,
                ft.VerticalDivider(width=1, color=theme.BORDER),
                self.content,
            ],
            expand=True,
            spacing=0,
        )
        initial_section = (
            "Historial de lecturas"
            if self.current_user["rol"] == "socio"
            else "Inicio"
        )
        self.navigate(initial_section)

    def logout(self) -> None:
        self.api.access_token = None
        self.current_user = None
        self.show_login()

    def navigate(self, section: str) -> None:
        self.selected_label.value = "Biblioteca UTN" if section == "Inicio" else section
        for button, (label, _) in zip(
            self.nav_column.controls, self.visible_nav_items
        ):
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
            "Usuarios": lambda: usuarios.build(self),
            "Historial de lecturas": lambda: historial.build(self),
            "Sedes": lambda: sedes.build(self),
            "Ejemplares": lambda: ejemplares.build(self),
            "Remitos": lambda: remitos.build(self),
            "Reservas": lambda: reservas.build(self),
            "Préstamos": lambda: prestamos.build(self),
            "Mis préstamos": lambda: mis_prestamos.build(self),
            "Reportes": lambda: reportes.build(self),
            "Notificaciones": lambda: notificaciones.build(self),
        }
        return views[section]

    def _build_navigation(self) -> None:
        self.nav_column.controls.clear()
        role = self.current_user["rol"] if self.current_user else ""
        if role == "socio":
            self.visible_nav_items = (
                ("Historial de lecturas", ft.Icons.HISTORY_OUTLINED),
                ("Mis préstamos", ft.Icons.SWAP_HORIZ_OUTLINED),
                ("Notificaciones", ft.Icons.NOTIFICATIONS_OUTLINED),
            )
        else:
            self.visible_nav_items = tuple(
                (label, icon)
                for label, icon in NAV_ITEMS
                if label != "Usuarios" or role == "admin"
            )
        for label, icon in self.visible_nav_items:
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
