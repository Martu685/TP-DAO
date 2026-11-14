from collections.abc import Callable
from typing import Any

import flet as ft

from frontend.ui.theme import ACCENT, BORDER, ERROR, INK, MUTED


def notify(page: ft.Page, message: str, error: bool = False) -> None:
    page.snack_bar = ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=ERROR if error else ACCENT,
    )
    page.open(page.snack_bar)


def empty_state(
    message: str, icon: Any = ft.Icons.INBOX_OUTLINED
) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(icon, size=36, color="#AAB1BA"),
                ft.Text(message, color=MUTED, text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
        alignment=ft.Alignment(0, 0),
        padding=48,
    )


def section_header(
    title: str,
    subtitle: str,
    action_label: str | None = None,
    action: Callable[..., Any] | None = None,
) -> ft.Row:
    actions: list[ft.Control] = []
    if action_label and action:
        actions.append(
            ft.FilledButton(action_label, icon=ft.Icons.ADD, on_click=action)
        )
    return ft.Row(
        [
            ft.Column(
                [
                    ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=INK),
                    ft.Text(subtitle, size=14, color=MUTED),
                ],
                spacing=5,
                expand=True,
            ),
            *actions,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def card(content: ft.Control, padding: int = 20) -> ft.Container:
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, BORDER),
        border_radius=14,
    )


def data_table(headers: list[str], rows: list[list[ft.Control]]) -> ft.Control:
    if not rows:
        return empty_state("Todavía no hay registros para mostrar.")
    return ft.Column(
        [
            ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text(label, weight=ft.FontWeight.W_600))
                    for label in headers
                ],
                rows=[
                    ft.DataRow(cells=[ft.DataCell(value) for value in row])
                    for row in rows
                ],
                column_spacing=22,
                horizontal_margin=8,
                data_row_min_height=58,
                heading_row_height=48,
            )
        ],
        scroll=ft.ScrollMode.AUTO,
    )


def open_form(
    page: ft.Page,
    title: str,
    fields: list[ft.Control],
    submit: Callable[[ft.AlertDialog], None],
) -> None:
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                fields, tight=True, spacing=14, scroll=ft.ScrollMode.AUTO
            ),
            width=420,
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: page.close(dialog)),
            ft.FilledButton("Guardar", on_click=lambda _: submit(dialog)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.open(dialog)


def text_input(label: str, **kwargs: Any) -> ft.TextField:
    return ft.TextField(label=label, border_radius=10, **kwargs)
