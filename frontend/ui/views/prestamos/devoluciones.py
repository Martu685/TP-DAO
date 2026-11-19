from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.api.client import ApiError
from frontend.ui.components import notify, open_form, text_input

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def actions(
    app: LibraryApp,
    prestamo: dict[str, Any],
    devoluciones_by_id: dict[int, dict[str, Any]],
) -> list[ft.Control]:
    if prestamo.get("tipo_prestamo") != "prestamo_local":
        return []

    return [
        ft.IconButton(
            icon=ft.Icons.KEYBOARD_RETURN,
            tooltip="Gestionar devolución",
            on_click=lambda _: _manage(app, prestamo, devoluciones_by_id),
        )
    ]


def _manage(
    app: LibraryApp,
    prestamo: dict[str, Any],
    devoluciones_by_id: dict[int, dict[str, Any]],
) -> None:
    devolucion_id = prestamo.get("devolucion_id")
    devolucion = devoluciones_by_id.get(devolucion_id)
    actions: list[ft.Control] = []
    details: list[ft.Control]
    if devolucion_id is None:
        if prestamo.get("fecha_devolucion") is not None:
            details = [
                ft.Text(
                    "El préstamo tiene fecha de devolución, pero no se encontró "
                    "el registro asociado.",
                    color=ft.Colors.AMBER_900,
                )
            ]
        else:
            details = [ft.Text("Todavía no se registró una devolución.")]
            actions.append(
                ft.FilledButton(
                    "Registrar devolución",
                    icon=ft.Icons.ADD,
                    on_click=lambda _: _start_register(app, prestamo),
                )
            )
    elif devolucion is None:
        details = [
            ft.Text(
                f"No se encontró la devolución #{devolucion_id} en la API.",
                color=ft.Colors.AMBER_900,
            ),
        ]
    else:
        details = [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED),
                title=ft.Text("Fecha"),
                subtitle=ft.Text(devolucion["fecha"]),
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.NOTES_OUTLINED),
                title=ft.Text("Observaciones"),
                subtitle=ft.Text(devolucion["observaciones"] or "Sin observaciones"),
            ),
        ]
        actions.extend(
            [
                ft.OutlinedButton(
                    "Editar",
                    icon=ft.Icons.EDIT_OUTLINED,
                    on_click=lambda _: _start_edit(app, devolucion),
                ),
                ft.OutlinedButton(
                    "Eliminar",
                    icon=ft.Icons.DELETE_OUTLINE,
                    on_click=lambda _: _start_delete(app, devolucion, prestamo),
                ),
            ]
        )

    actions.append(
        ft.TextButton("Cerrar", on_click=lambda _: app.page.pop_dialog())
    )
    app.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Devolución del préstamo #{prestamo['id']}"),
            content=ft.Container(
                content=ft.Column(details, tight=True, spacing=6),
                width=420,
            ),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def _start_register(app: LibraryApp, prestamo: dict[str, Any]) -> None:
    app.page.pop_dialog()
    _register(app, prestamo)


def _start_edit(app: LibraryApp, devolucion: dict[str, Any]) -> None:
    app.page.pop_dialog()
    _edit(app, devolucion)


def _start_delete(
    app: LibraryApp,
    devolucion: dict[str, Any],
    prestamo: dict[str, Any],
) -> None:
    app.page.pop_dialog()
    _confirm_delete(app, devolucion, prestamo)


def _register(app: LibraryApp, prestamo: dict[str, Any]) -> None:
    return_date = text_input("Fecha de devolución", value=date.today().isoformat())
    condition = ft.Dropdown(
        label="Estado físico",
        value="Bueno",
        options=[
            ft.dropdown.Option(value, value)
            for value in ("Bueno", "Dañado", "Extraviado", "Destruido")
        ],
        border_radius=10,
    )
    observations = text_input(
        "Observaciones (opcional)", multiline=True, min_lines=2, max_lines=4
    )

    def submit() -> None:
        try:
            parsed_date = date.fromisoformat(return_date.value.strip())
            app.api.request(
                f"/api/devolucion/prestamo/{prestamo['id']}",
                "POST",
                {
                    "fecha": parsed_date.isoformat(),
                    "observaciones": observations.value.strip() or None,
                    "estado_fisico": condition.value,
                },
            )
        except ValueError:
            notify(app.page, "Usá una fecha válida con formato AAAA-MM-DD.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        app.page.pop_dialog()
        notify(app.page, "Devolución registrada.")
        app.navigate("Préstamos")

    open_form(
        app.page,
        f"Devolución del préstamo #{prestamo['id']}",
        [return_date, condition, observations],
        submit,
    )


def _edit(app: LibraryApp, devolucion: dict[str, Any]) -> None:
    return_date = text_input("Fecha de devolución", value=devolucion["fecha"])
    observations = text_input(
        "Observaciones (opcional)",
        value=devolucion["observaciones"] or "",
        multiline=True,
        min_lines=2,
        max_lines=4,
    )

    def submit() -> None:
        try:
            parsed_date = date.fromisoformat(return_date.value.strip())
            app.api.request(
                f"/api/devolucion/{devolucion['id']}",
                "PUT",
                {
                    "fecha": parsed_date.isoformat(),
                    "observaciones": observations.value.strip() or None,
                },
            )
        except ValueError:
            notify(app.page, "Usá una fecha válida con formato AAAA-MM-DD.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        app.page.pop_dialog()
        notify(app.page, "Devolución actualizada.")
        app.navigate("Préstamos")

    open_form(
        app.page,
        f"Editar devolución #{devolucion['id']}",
        [return_date, observations],
        submit,
    )


def _confirm_delete(
    app: LibraryApp,
    devolucion: dict[str, Any],
    prestamo: dict[str, Any],
) -> None:
    def delete(_: Any) -> None:
        try:
            app.api.request(f"/api/devolucion/{devolucion['id']}", "DELETE")
        except ApiError as error:
            notify(app.page, str(error), True)
            return

        app.page.pop_dialog()
        notify(
            app.page,
            f"Devolución eliminada. El préstamo #{prestamo['id']} fue reabierto.",
        )
        app.navigate("Préstamos")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Eliminar devolución"),
        content=ft.Text(
            f"¿Eliminar la devolución del préstamo #{prestamo['id']}? "
            "El préstamo se reabrirá y el ejemplar volverá a figurar como prestado."
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton(
                "Eliminar devolución",
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=delete,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)
