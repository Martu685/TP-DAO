from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import flet as ft

from frontend.api.client import ApiError
from frontend.ui.components import card, data_table, notify, section_header, text_input

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    remitos = app.api.request("/api/remito")
    remito_states = app.api.request("/api/estado/remito")
    loans = app.api.request("/api/prestamo-interbibliotecario")
    branches = app.api.request("/api/sede")
    copies = app.api.request("/api/ejemplar")
    books = app.api.request("/api/libro")
    details = app.api.request("/api/detalle-remito")

    state_names = {state["id"]: state["descripcion"] for state in remito_states}
    branch_names = {branch["id"]: branch["nombre"] for branch in branches}
    copies_by_id = {copy["id"]: copy for copy in copies}
    book_names = {book["id"]: book["titulo"] for book in books}
    loans_by_remito: dict[int, list[dict[str, Any]]] = {}
    for loan in loans:
        if loan["remito_id"] is not None:
            loans_by_remito.setdefault(loan["remito_id"], []).append(loan)
    details_by_remito: dict[int, list[dict[str, Any]]] = {}
    for detail in details:
        details_by_remito.setdefault(detail["remito_id"], []).append(detail)

    search = text_input(
        "Buscar por número, sedes o estado", prefix_icon=ft.Icons.SEARCH
    )
    table = ft.Container()

    def render_rows(_: Any = None) -> None:
        term = search.value.strip().casefold()
        rows = []
        for remito in remitos:
            status_name = state_names.get(remito["estado_remito_id"], "Desconocido")
            associated_loans = loans_by_remito.get(remito["id"], [])
            route = _route_label(associated_loans, branch_names)
            if term not in f"{remito['numero']} {route} {status_name}".casefold():
                continue
            rows.append(
                [
                    ft.Text(remito["numero"], weight=ft.FontWeight.W_500),
                    ft.Text(route),
                    ft.Text(remito["fecha_emision"]),
                    ft.Text(remito["fecha_recepcion"] or "—"),
                    ft.Text(str(len(details_by_remito.get(remito["id"], [])))),
                    ft.Text(status_name),
                    _remito_actions(
                        app,
                        remito,
                        status_name,
                        details_by_remito.get(remito["id"], []),
                        copies_by_id,
                        book_names,
                    ),
                ]
            )
        table.content = data_table(
            [
                "N.º",
                "Origen → destino",
                "Emisión",
                "Recepción",
                "Ejemplares",
                "Estado",
                "Acciones",
            ],
            rows,
        )
        app.page.update()

    search.on_change = render_rows
    view = ft.Column(
        [
            section_header(
                "Remitos",
                "Prepará, despachá y recibí envíos interbibliotecarios.",
                "Nuevo remito",
                lambda _: _new_remito(app),
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


def _route_label(
    loans: list[dict[str, Any]], branch_names: dict[int, str]
) -> str:
    if not loans:
        return "—"
    loan = loans[0]
    return (
        f"{branch_names.get(loan['sede_origen_id'], '—')} → "
        f"{branch_names.get(loan['sede_destino_id'], '—')}"
    )


def _remito_actions(
    app: LibraryApp,
    remito: dict[str, Any],
    status_name: str,
    details: list[dict[str, Any]],
    copies_by_id: dict[int, dict[str, Any]],
    book_names: dict[int, str],
) -> ft.Row:
    normalized_status = status_name.casefold()
    actions: list[ft.Control] = [
        ft.TextButton(
            "Detalle",
            on_click=lambda _, selected=remito, selected_details=details, selected_status=status_name: (
                _show_details(
                    app,
                    selected,
                    selected_details,
                    selected_status,
                    copies_by_id,
                    book_names,
                )
            ),
        ),
        ft.TextButton(
            "Incidencias",
            on_click=lambda _, selected=remito, selected_status=status_name: (
                _show_incidences(app, selected, selected_status)
            ),
        ),
    ]
    if normalized_status == "preparado":
        actions.append(
            ft.TextButton(
                "Despachar",
                on_click=lambda _, selected=remito: _confirm_transition(
                    app,
                    selected,
                    "Despachar remito",
                    f"¿Querés despachar el remito {selected['numero']}?",
                    "despachar",
                    "Remito despachado correctamente.",
                ),
            )
        )
    elif normalized_status in {"en tránsito", "incidencia"}:
        actions.append(
            ft.TextButton(
                "Recibir",
                on_click=lambda _, selected=remito: _confirm_transition(
                    app,
                    selected,
                    "Recibir remito",
                    f"¿Confirmás la recepción del remito {selected['numero']}?",
                    "recibir",
                    "Remito recibido correctamente.",
                ),
            )
        )
    return ft.Row(actions, spacing=0, wrap=True)


def _show_details(
    app: LibraryApp,
    remito: dict[str, Any],
    details: list[dict[str, Any]],
    status_name: str,
    copies_by_id: dict[int, dict[str, Any]],
    book_names: dict[int, str],
) -> None:
    items: list[ft.Control] = []
    for detail in details:
        copy = copies_by_id.get(detail["ejemplar_id"], {})
        title = book_names.get(copy.get("libro_id"), "Libro no encontrado")
        code = copy.get("codigo", f"Ejemplar #{detail['ejemplar_id']}")
        item_actions: list[ft.Control] = [ft.Text(f"{code} · {title}")]
        if status_name.casefold() == "preparado":
            item_actions.append(
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="Quitar del remito",
                    on_click=lambda _, selected_detail=detail: (
                        _confirm_delete_detail(app, selected_detail, remito)
                    ),
                )
            )
        items.append(ft.Row(item_actions, alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
    if not items:
        items.append(ft.Text("El remito no tiene ejemplares asociados."))

    actions: list[ft.Control] = [
        ft.TextButton("Cerrar", on_click=lambda _: app.page.pop_dialog())
    ]
    if status_name.casefold() == "preparado":
        actions.insert(
            0,
            ft.FilledButton(
                "Agregar ejemplar",
                icon=ft.Icons.ADD,
                on_click=lambda _: _open_add_detail(app, remito, details),
            ),
        )

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Detalle del remito {remito['numero']}"),
        content=ft.Container(
            content=ft.Column(items, tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
            width=460,
            height=300,
        ),
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _confirm_delete_detail(
    app: LibraryApp,
    detail: dict[str, Any],
    remito: dict[str, Any],
) -> None:
    def delete(_: Any) -> None:
        try:
            app.api.request(
                f"/api/detalle-remito/{detail['id']}",
                "DELETE",
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Ejemplar quitado del remito.")
        app.navigate("Remitos")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Quitar ejemplar"),
        content=ft.Text(
            f"¿Querés quitar el ejemplar #{detail['ejemplar_id']} "
            f"del remito {remito['numero']}?"
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton("Quitar", on_click=delete),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _open_add_detail(
    app: LibraryApp,
    remito: dict[str, Any],
    details: list[dict[str, Any]],
) -> None:
    app.page.pop_dialog()
    try:
        loans = app.api.request("/api/prestamo-interbibliotecario")
        copies = app.api.request("/api/ejemplar")
        books = app.api.request("/api/libro")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    existing_copy_ids = {detail["ejemplar_id"] for detail in details}
    eligible_copies = [
        copy
        for copy in copies
        if copy["id"] not in existing_copy_ids
        and any(
            loan["remito_id"] == remito["id"]
            and loan["ejemplar_id"] == copy["id"]
            for loan in loans
        )
    ]
    if not eligible_copies:
        notify(app.page, "No hay ejemplares asociados para agregar.", True)
        return

    book_names = {book["id"]: book["titulo"] for book in books}
    copy = ft.Dropdown(
        label="Ejemplar",
        options=[
            ft.dropdown.Option(
                str(item["id"]),
                f"{item['codigo']} · "
                f"{book_names.get(item['libro_id'], 'Libro sin título')}",
            )
            for item in eligible_copies
        ],
        border_radius=10,
    )

    def submit(_: Any) -> None:
        if not copy.value:
            notify(app.page, "Seleccioná un ejemplar.", True)
            return
        try:
            app.api.request(
                "/api/detalle-remito",
                "POST",
                {
                    "remito_id": remito["id"],
                    "ejemplar_id": int(copy.value),
                },
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Ejemplar agregado al remito.")
        app.navigate("Remitos")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Agregar ejemplar"),
        content=ft.Container(content=copy, width=460),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton("Agregar", on_click=submit),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _show_incidences(
    app: LibraryApp, remito: dict[str, Any], status_name: str
) -> None:
    try:
        incidences = app.api.request(f"/api/remito/{remito['id']}/incidencias")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    items: list[ft.Control] = []
    for incidence in incidences:
        items.append(
            ft.Column(
                [
                    ft.Text(
                        f"{incidence['fecha']} · "
                        f"{'Resuelta' if incidence['resuelta'] else 'Pendiente'}",
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(incidence["descripcion"]),
                    ft.Divider(),
                ],
                spacing=4,
            )
        )
    if not items:
        items.append(ft.Text("Este remito todavía no tiene incidencias."))

    actions: list[ft.Control] = [
        ft.TextButton("Cerrar", on_click=lambda _: app.page.pop_dialog())
    ]
    if status_name.casefold() == "en tránsito":
        actions.insert(
            0,
            ft.FilledButton(
                "Registrar incidencia",
                on_click=lambda _: _open_incidence_form(app, remito),
            ),
        )
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Incidencias · Remito {remito['numero']}"),
        content=ft.Container(
            content=ft.Column(items, tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
            width=460,
            height=300,
        ),
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _open_incidence_form(app: LibraryApp, remito: dict[str, Any]) -> None:
    app.page.pop_dialog()
    description = text_input(
        "Descripción de la incidencia", multiline=True, min_lines=3, max_lines=6
    )

    def submit(_: Any) -> None:
        if not description.value.strip():
            notify(app.page, "Describí la incidencia.", True)
            return
        try:
            app.api.request(
                f"/api/remito/{remito['id']}/incidencias",
                "POST",
                {"descripcion": description.value.strip()},
            )
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Incidencia registrada correctamente.")
        app.navigate("Remitos")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Incidencia · Remito {remito['numero']}"),
        content=ft.Container(content=description, width=460),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton("Registrar", on_click=submit),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _confirm_transition(
    app: LibraryApp,
    remito: dict[str, Any],
    title: str,
    message: str,
    action: str,
    success_message: str,
) -> None:
    def confirm(_: Any) -> None:
        try:
            app.api.request(f"/api/remito/{remito['id']}/{action}", "POST")
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, success_message)
        app.navigate("Remitos")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=ft.Text(message),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton(title, on_click=confirm),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)


def _new_remito(app: LibraryApp) -> None:
    try:
        loans = app.api.request("/api/prestamo-interbibliotecario")
        loan_states = app.api.request("/api/estado/prestamo")
        branches = app.api.request("/api/sede")
        copies = app.api.request("/api/ejemplar")
        books = app.api.request("/api/libro")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    pending_state_ids = {
        state["id"]
        for state in loan_states
        if state["descripcion"].casefold() == "pendiente"
    }
    eligible_loans = [
        loan
        for loan in loans
        if loan["remito_id"] is None
        and loan["estado_prestamo_id"] in pending_state_ids
    ]
    if not eligible_loans:
        notify(
            app.page,
            "No hay préstamos interbibliotecarios pendientes para incluir.",
            True,
        )
        return

    branch_names = {branch["id"]: branch["nombre"] for branch in branches}
    copies_by_id = {copy["id"]: copy for copy in copies}
    book_names = {book["id"]: book["titulo"] for book in books}
    checkboxes: dict[int, ft.Checkbox] = {}
    loan_controls: list[ft.Control] = []
    for loan in eligible_loans:
        copy = copies_by_id.get(loan["ejemplar_id"], {})
        code = copy.get("codigo", f"Ejemplar #{loan['ejemplar_id']}")
        title = book_names.get(copy.get("libro_id"), "Libro no encontrado")
        route = (
            f"{branch_names.get(loan['sede_origen_id'], '—')} → "
            f"{branch_names.get(loan['sede_destino_id'], '—')}"
        )
        checkbox = ft.Checkbox(
            label=f"Préstamo #{loan['id']} · {code} · {title} · {route}"
        )
        checkboxes[loan["id"]] = checkbox
        loan_controls.append(checkbox)

    number = text_input("Número de remito")
    issue_date = text_input(
        "Fecha de emisión (AAAA-MM-DD)", value=date.today().isoformat()
    )

    def submit(_: Any) -> None:
        selected_ids = [
            loan_id for loan_id, checkbox in checkboxes.items() if checkbox.value
        ]
        if not selected_ids:
            notify(app.page, "Seleccioná al menos un préstamo.", True)
            return
        selected = [
            loan for loan in eligible_loans if loan["id"] in selected_ids
        ]
        routes = {
            (loan["sede_origen_id"], loan["sede_destino_id"]) for loan in selected
        }
        if len(routes) != 1:
            notify(
                app.page,
                "Los préstamos de un remito deben compartir origen y destino.",
                True,
            )
            return
        if not number.value.strip():
            notify(app.page, "Ingresá el número de remito.", True)
            return
        try:
            emission_date = date.fromisoformat(issue_date.value.strip())
            app.api.request(
                "/api/remito",
                "POST",
                {
                    "numero": number.value.strip(),
                    "fecha_emision": emission_date.isoformat(),
                    "prestamos_inter_ids": selected_ids,
                },
            )
        except ValueError:
            notify(app.page, "Usá una fecha válida con formato AAAA-MM-DD.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Remito creado correctamente.")
        app.navigate("Remitos")

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Nuevo remito"),
        content=ft.Container(
            content=ft.Column(
                [
                    number,
                    issue_date,
                    ft.Text("Préstamos pendientes", weight=ft.FontWeight.W_600),
                    ft.Container(
                        content=ft.Column(
                            loan_controls,
                            spacing=4,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        height=260,
                    ),
                ],
                tight=True,
                spacing=14,
            ),
            width=560,
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: app.page.pop_dialog()),
            ft.FilledButton("Crear remito", on_click=submit),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    app.page.show_dialog(dialog)
