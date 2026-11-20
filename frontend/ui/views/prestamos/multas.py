from __future__ import annotations

import math
from datetime import date
from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.api.client import ApiError
from frontend.ui.components import (
    notify,
    open_form,
    text_input,
    update_form_errors,
)

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def actions(
    app: LibraryApp,
    prestamo: dict[str, Any],
    multas_by_id: dict[int, dict[str, Any]],
) -> list[ft.Control]:
    return [
        ft.IconButton(
            icon=ft.Icons.RECEIPT_LONG_OUTLINED,
            tooltip="Gestionar multa",
            on_click=lambda _: _manage(app, prestamo, multas_by_id),
        ),
    ]


def _manage(
    app: LibraryApp,
    prestamo: dict[str, Any],
    multas_by_id: dict[int, dict[str, Any]],
) -> None:
    multa_id = prestamo.get("multa_id")
    multa = multas_by_id.get(multa_id)
    actions: list[ft.Control] = []
    if multa_id is None:
        details = ft.Text("Este préstamo todavía no tiene una multa asociada.")
        actions.append(
            ft.FilledButton(
                "Registrar multa",
                icon=ft.Icons.ADD,
                on_click=lambda _: _start_register(app, prestamo),
            )
        )
    elif multa is None:
        details = ft.Text(
            f"No se encontró la multa #{multa_id} en la API.",
            color=ft.Colors.AMBER_900,
        )
    else:
        details = ft.Text(
            "Hay una multa asociada. Elegí una acción para consultar o administrar "
            "sus datos."
        )
        actions.extend(
            [
                ft.OutlinedButton(
                    "Consultar multa",
                    icon=ft.Icons.VISIBILITY_OUTLINED,
                    on_click=lambda _: _start_consult(app, prestamo, multa),
                ),
                ft.OutlinedButton(
                    "Editar",
                    icon=ft.Icons.EDIT_OUTLINED,
                    on_click=lambda _: _start_edit(app, multa),
                ),
                ft.OutlinedButton(
                    "Eliminar",
                    icon=ft.Icons.DELETE_OUTLINE,
                    on_click=lambda _: _start_delete(app, multa, prestamo),
                ),
            ]
        )

    actions.append(
        ft.TextButton("Cerrar", on_click=lambda _: app.page.pop_dialog())
    )
    app.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Multa del préstamo #{prestamo['id']}"),
            content=ft.Container(content=details, width=420),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _fine_details(multa: dict[str, Any]) -> ft.Column:
    return ft.Column(
        [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.ATTACH_MONEY),
                title=ft.Text("Monto"),
                subtitle=ft.Text(f"${multa['monto']:,.2f}"),
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED),
                title=ft.Text("Fecha"),
                subtitle=ft.Text(multa["fecha"]),
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.INFO_OUTLINE),
                title=ft.Text("Motivo"),
                subtitle=ft.Text(multa["motivo"]),
            ),
        ],
        tight=True,
        spacing=6,
    )


def _consult(
    app: LibraryApp,
    prestamo: dict[str, Any],
    multa: dict[str, Any],
) -> None:
    app.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Multa asociada al préstamo #{prestamo['id']}"),
            content=ft.Container(content=_fine_details(multa), width=420),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda _: app.page.pop_dialog())
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _start_register(app: LibraryApp, prestamo: dict[str, Any]) -> None:
    app.page.pop_dialog()
    _register(app, prestamo)


def _start_edit(app: LibraryApp, multa: dict[str, Any]) -> None:
    app.page.pop_dialog()
    _edit(app, multa)


def _start_consult(
    app: LibraryApp,
    prestamo: dict[str, Any],
    multa: dict[str, Any],
) -> None:
    app.page.pop_dialog()
    _consult(app, prestamo, multa)


def _start_delete(
    app: LibraryApp,
    multa: dict[str, Any],
    prestamo: dict[str, Any],
) -> None:
    app.page.pop_dialog()
    _confirm_delete(app, multa, prestamo)


def _register(app: LibraryApp, prestamo: dict[str, Any]) -> None:
    amount = text_input("Monto", keyboard_type=ft.KeyboardType.NUMBER)
    fine_date = text_input("Fecha", value=date.today().isoformat())
    reason = text_input("Motivo")

    def submit() -> None:
        fields = [amount, fine_date, reason]
        errors = [
            (field, "Completá este campo.")
            for field in fields
            if not field.value.strip()
        ]
        if update_form_errors(app.page, fields, errors):
            return
        try:
            parsed_amount = float(amount.value.strip())
        except ValueError:
            update_form_errors(
                app.page, fields, [(amount, "Ingresá un monto numérico válido.")]
            )
            return
        if not math.isfinite(parsed_amount) or parsed_amount < 0:
            update_form_errors(
                app.page, fields, [(amount, "El monto debe ser un número no negativo.")]
            )
            return
        try:
            parsed_date = date.fromisoformat(fine_date.value.strip())
        except ValueError:
            update_form_errors(
                app.page, fields, [(fine_date, "Usá el formato AAAA-MM-DD.")]
            )
            return
        try:
            app.api.request(
                "/api/multa",
                "POST",
                {
                    "monto": parsed_amount,
                    "fecha": parsed_date.isoformat(),
                    "motivo": reason.value.strip(),
                    "prestamo_id": prestamo["id"],
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        app.page.pop_dialog()
        notify(app.page, "Multa registrada y asociada al préstamo.")
        app.navigate("Préstamos")

    open_form(
        app.page,
        f"Registrar multa del préstamo #{prestamo['id']}",
        [amount, fine_date, reason],
        submit,
    )


def _edit(app: LibraryApp, multa: dict[str, Any]) -> None:
    amount = text_input(
        "Monto",
        value=str(multa["monto"]),
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    fine_date = text_input("Fecha", value=multa["fecha"])
    reason = text_input("Motivo", value=multa["motivo"])

    def submit() -> None:
        fields = [amount, fine_date, reason]
        errors = [
            (field, "Completá este campo.")
            for field in fields
            if not field.value.strip()
        ]
        if update_form_errors(app.page, fields, errors):
            return
        try:
            parsed_amount = float(amount.value.strip())
        except ValueError:
            update_form_errors(
                app.page, fields, [(amount, "Ingresá un monto numérico válido.")]
            )
            return
        if not math.isfinite(parsed_amount) or parsed_amount < 0:
            update_form_errors(
                app.page, fields, [(amount, "El monto debe ser un número no negativo.")]
            )
            return
        try:
            parsed_date = date.fromisoformat(fine_date.value.strip())
        except ValueError:
            update_form_errors(
                app.page, fields, [(fine_date, "Usá el formato AAAA-MM-DD.")]
            )
            return
        try:
            app.api.request(
                f"/api/multa/{multa['id']}",
                "PUT",
                {
                    "monto": parsed_amount,
                    "fecha": parsed_date.isoformat(),
                    "motivo": reason.value.strip(),
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        app.page.pop_dialog()
        notify(app.page, "Multa actualizada.")
        app.navigate("Préstamos")

    open_form(
        app.page,
        f"Editar multa #{multa['id']}",
        [amount, fine_date, reason],
        submit,
    )


def _confirm_delete(
    app: LibraryApp,
    multa: dict[str, Any],
    prestamo: dict[str, Any],
) -> None:
    def delete(_: Any) -> None:
        try:
            app.api.request(f"/api/multa/{multa['id']}", "DELETE")
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        app.page.pop_dialog()
        notify(app.page, f"Multa eliminada del préstamo #{prestamo['id']}.")
        app.navigate("Préstamos")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Eliminar multa"),
        content=ft.Text(
            f"¿Eliminar la multa #{multa['id']} del préstamo #{prestamo['id']}?"
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton(
                "Eliminar multa",
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=delete,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)
