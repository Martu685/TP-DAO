from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from frontend.api.client import ApiError
from frontend.ui.components import (
    card,
    data_table,
    empty_state,
    section_header,
)

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    is_member = bool(app.current_user and app.current_user["rol"] == "socio")
    table = ft.Container()

    def render_notifications(_: object = None) -> None:
        try:
            notifications = app.api.request("/api/notificacion")
        except ApiError as error:
            table.content = empty_state(
                f"No se pudieron cargar las notificaciones: {error}",
                ft.Icons.CLOUD_OFF_OUTLINED,
            )
        else:
            if notifications:
                headers = ["Fecha", "Canal", "Mensaje"]
                rows = [
                    [
                        ft.Text(str(notification["fecha"])),
                        ft.Text(notification["canal"]),
                        ft.Text(notification["mensaje"]),
                    ]
                    for notification in notifications
                ]
                if not is_member:
                    headers.insert(0, "Socio")
                    for notification, row in zip(notifications, rows):
                        row.insert(0, ft.Text(f"#{notification['socio_id']}"))
                table.content = data_table(headers, rows)
            else:
                table.content = empty_state(
                    "Todavía no recibiste notificaciones."
                    if is_member
                    else "No hay notificaciones para mostrar.",
                    ft.Icons.NOTIFICATIONS_NONE_OUTLINED,
                )
        app.page.update()

    render_notifications()
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Container(
                        content=section_header(
                            "Mis notificaciones" if is_member else "Notificaciones",
                            "Avisos automáticos de cambios en tus reservas y préstamos."
                            if is_member
                            else "Avisos automáticos por cambios de estado en reservas "
                            "y préstamos.",
                        ),
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="Actualizar notificaciones",
                        on_click=render_notifications,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            card(table, 8),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
