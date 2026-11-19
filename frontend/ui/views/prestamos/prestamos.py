from __future__ import annotations

from datetime import date, timedelta
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
from frontend.ui.views.prestamos import devoluciones, multas

if TYPE_CHECKING:
    from frontend.ui.app import LibraryApp


def build(app: LibraryApp) -> ft.Control:
    prestamos = app.api.request("/api/prestamo")
    prestamos_inter = app.api.request("/api/prestamo-interbibliotecario")
    devoluciones_by_id = {
        devolucion["id"]: devolucion
        for devolucion in app.api.request("/api/devolucion")
    }
    multas_by_id = {
        multa["id"]: multa for multa in app.api.request("/api/multa")
    }
    ejemplares = app.api.request("/api/ejemplar")
    books = app.api.request("/api/libro")
    states = app.api.request("/api/estado/prestamo")
    branches = app.api.request("/api/sede")
    ejemplares_by_id = {item["id"]: item for item in ejemplares}
    book_names = {book["id"]: book["titulo"] for book in books}
    state_names = {state["id"]: state["descripcion"] for state in states}
    branch_names = {branch["id"]: branch["nombre"] for branch in branches}
    inter_by_id = {loan["id"]: loan for loan in prestamos_inter}

    return ft.Column(
        [
            section_header(
                "Préstamos",
                "Seguimiento de préstamos locales e interbibliotecarios.",
            ),
            ft.Row(
                [
                    ft.Container(expand=True),
                    ft.OutlinedButton(
                        "Nuevo interbibliotecario",
                        icon=ft.Icons.SWAP_HORIZ_OUTLINED,
                        on_click=lambda _: _new_interlibrary_loan(app),
                    ),
                    ft.FilledButton(
                        "Nuevo préstamo local",
                        icon=ft.Icons.ADD,
                        on_click=lambda _: _new_prestamo(app),
                    ),
                ],
                spacing=10,
            ),
            card(
                data_table(
                    [
                        "N.º",
                        "Tipo / recorrido",
                        "Libro / ejemplar",
                        "Inicio",
                        "Vencimiento",
                        "Estado",
                        "Gestión",
                    ],
                    [
                        _prestamo_row(
                            app,
                            prestamo,
                            inter_by_id,
                            ejemplares_by_id,
                            book_names,
                            state_names,
                            branch_names,
                            devoluciones_by_id,
                            multas_by_id,
                        )
                        for prestamo in prestamos
                    ],
                ),
                8,
            ),
        ],
        spacing=18,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


def _prestamo_row(
    app: LibraryApp,
    prestamo: dict[str, Any],
    inter_by_id: dict[int, dict[str, Any]],
    ejemplares_by_id: dict[int, dict[str, Any]],
    book_names: dict[int, str],
    state_names: dict[int, str],
    branch_names: dict[int, str],
    devoluciones_by_id: dict[int, dict[str, Any]],
    multas_by_id: dict[int, dict[str, Any]],
) -> list[ft.Control]:
    copy = ejemplares_by_id.get(prestamo["ejemplar_id"], {})
    is_interlibrary = prestamo.get("tipo_prestamo") == "prestamo_interbibliotecario"
    inter_loan = inter_by_id.get(prestamo["id"], {}) if is_interlibrary else {}
    actions = devoluciones.actions(app, prestamo, devoluciones_by_id)
    actions.extend(multas.actions(app, prestamo, multas_by_id))
    if is_interlibrary:
        if prestamo.get("fecha_devolucion") is None:
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    tooltip="Editar vencimiento",
                    on_click=lambda _, selected=inter_loan: _edit_interlibrary_due_date(
                        app, selected
                    ),
                )
            )
        actions.append(
            ft.IconButton(
                icon=ft.Icons.LOCAL_SHIPPING_OUTLINED,
                tooltip="Ver remitos",
                on_click=lambda _: app.navigate("Remitos"),
            )
        )
    kind = "Interbibliotecario" if is_interlibrary else "Local"
    if is_interlibrary:
        route = (
            f"{branch_names.get(inter_loan.get('sede_origen_id'), '—')} → "
            f"{branch_names.get(inter_loan.get('sede_destino_id'), '—')}"
        )
        kind = f"{kind}\n{route}"
    return [
        ft.Text(f"#{prestamo['id']}"),
        ft.Text(kind, weight=ft.FontWeight.W_500),
        ft.Text(
            f"{book_names.get(copy.get('libro_id'), 'Libro')} · "
            f"{copy.get('codigo', '—')}",
            weight=ft.FontWeight.W_500,
        ),
        ft.Text(prestamo["fecha_inicio"]),
        ft.Text(prestamo["fecha_vencimiento"]),
        ft.Text(state_names.get(prestamo["estado_prestamo_id"], "—")),
        ft.Row(actions, spacing=4, wrap=False),
    ]


def _new_interlibrary_loan(app: LibraryApp) -> None:
    try:
        branches = [
            branch
            for branch in app.api.request("/api/sede")
            if branch["activa"]
        ]
        available_copies = app.api.request("/api/ejemplar/disponibilidad")
        books = app.api.request("/api/libro")
        states = app.api.request("/api/estado/prestamo")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    pending_state = next(
        (state for state in states if state["descripcion"].casefold() == "pendiente"),
        None,
    )
    if pending_state is None:
        notify(app.page, "No se encontró el estado 'Pendiente' en la API.", True)
        return
    if len(branches) < 2:
        notify(app.page, "Se necesitan al menos dos sedes activas.", True)
        return
    if not available_copies:
        notify(app.page, "No hay ejemplares disponibles para prestar.", True)
        return

    branch_options = [
        ft.dropdown.Option(str(branch["id"]), branch["nombre"])
        for branch in branches
    ]
    book_names = {book["id"]: book["titulo"] for book in books}
    origin = ft.Dropdown(
        label="Sede de origen",
        options=branch_options,
        border_radius=10,
    )
    destination = ft.Dropdown(
        label="Sede de destino",
        options=branch_options,
        border_radius=10,
    )
    copy = ft.Dropdown(
        label="Ejemplar disponible",
        options=[],
        border_radius=10,
    )
    start = text_input("Fecha de inicio", value=date.today().isoformat())
    due = text_input(
        "Fecha de vencimiento",
        value=(date.today() + timedelta(days=14)).isoformat(),
    )

    def update_choices(_: Any = None) -> None:
        selected_origin = int(origin.value) if origin.value else None
        destination.options = [
            ft.dropdown.Option(str(branch["id"]), branch["nombre"])
            for branch in branches
            if branch["id"] != selected_origin
        ]
        if destination.value and int(destination.value) == selected_origin:
            destination.value = None
        copy.options = [
            ft.dropdown.Option(
                str(item["id"]),
                f"{item['codigo']} · "
                f"{book_names.get(item['libro_id'], 'Libro sin título')}",
            )
            for item in available_copies
            if selected_origin is None or item["sede_id"] == selected_origin
        ]
        copy.value = None
        app.page.update()

    origin.on_change = update_choices
    update_choices()

    def submit() -> None:
        if not all(control.value for control in (origin, destination, copy)):
            notify(app.page, "Seleccioná origen, destino y ejemplar.", True)
            return
        try:
            start_date = date.fromisoformat(start.value.strip())
            due_date = date.fromisoformat(due.value.strip())
            if due_date < start_date:
                notify(
                    app.page,
                    "El vencimiento no puede ser anterior al inicio.",
                    True,
                )
                return
            app.api.request(
                "/api/prestamo-interbibliotecario",
                "POST",
                {
                    "fecha_inicio": start_date.isoformat(),
                    "fecha_vencimiento": due_date.isoformat(),
                    "fecha_devolucion": None,
                    "estado_prestamo_id": pending_state["id"],
                    "ejemplar_id": int(copy.value),
                    "multa_id": None,
                    "devolucion_id": None,
                    "sede_origen_id": int(origin.value),
                    "sede_destino_id": int(destination.value),
                    "remito_id": None,
                },
            )
        except ValueError:
            notify(app.page, "Usá fechas válidas con formato AAAA-MM-DD.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(
            app.page,
            "Préstamo interbibliotecario creado. Asociálo a un remito desde la vista Remitos.",
        )
        app.navigate("Préstamos")

    open_form(
        app.page,
        "Crear préstamo interbibliotecario",
        [origin, destination, copy, start, due],
        submit,
    )


def _edit_interlibrary_due_date(
    app: LibraryApp, prestamo: dict[str, Any]
) -> None:
    due = text_input(
        "Nueva fecha de vencimiento",
        value=prestamo["fecha_vencimiento"],
    )

    def submit() -> None:
        try:
            due_date = date.fromisoformat(due.value.strip())
            start_date = date.fromisoformat(prestamo["fecha_inicio"])
            if due_date < start_date:
                notify(
                    app.page,
                    "El vencimiento no puede ser anterior al inicio.",
                    True,
                )
                return
            app.api.request(
                f"/api/prestamo-interbibliotecario/{prestamo['id']}",
                "PUT",
                {
                    "fecha_inicio": prestamo["fecha_inicio"],
                    "fecha_vencimiento": due_date.isoformat(),
                    "fecha_devolucion": prestamo["fecha_devolucion"],
                    "estado_prestamo_id": prestamo["estado_prestamo_id"],
                    "ejemplar_id": prestamo["ejemplar_id"],
                    "multa_id": prestamo["multa_id"],
                    "devolucion_id": prestamo["devolucion_id"],
                    "sede_origen_id": prestamo["sede_origen_id"],
                    "sede_destino_id": prestamo["sede_destino_id"],
                    "remito_id": prestamo["remito_id"],
                },
            )
        except ValueError:
            notify(app.page, "Usá una fecha válida con formato AAAA-MM-DD.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Fecha de vencimiento actualizada.")
        app.navigate("Préstamos")

    open_form(
        app.page,
        f"Editar vencimiento del préstamo #{prestamo['id']}",
        [due],
        submit,
    )


def _new_prestamo(app: LibraryApp) -> None:
    try:
        members = [
            member
            for member in app.api.request("/api/socio")
            if member["habilitado"]
        ]
        branches = [
            branch
            for branch in app.api.request("/api/sede")
            if branch["activa"]
        ]
        ejemplares = app.api.request("/api/ejemplar/disponibilidad")
        books = app.api.request("/api/libro")
        states = app.api.request("/api/estado/prestamo")
    except ApiError as error:
        notify(app.page, str(error), True)
        return

    if not members or not branches or not ejemplares:
        notify(
            app.page,
            "Se necesita al menos un socio habilitado, una sede activa y "
            "un ejemplar disponible.",
            True,
        )
        return

    member_options = [
        ft.dropdown.Option(
            str(item["id"]), f"{item['apellido']}, {item['nombre']} · {item['dni']}"
        )
        for item in members
    ]
    branch_options = [
        ft.dropdown.Option(str(item["id"]), item["nombre"]) for item in branches
    ]
    book_names = {book["id"]: book["titulo"] for book in books}
    copy_options = [
        ft.dropdown.Option(
            str(item["id"]),
            f"{item['codigo']} · {book_names.get(item['libro_id'], 'Libro sin título')}",
        )
        for item in ejemplares
    ]
    initial_state = next(
        (state for state in states if state["descripcion"].casefold() == "activo"),
        None,
    )
    if initial_state is None:
        notify(
            app.page, "No se encontró el estado inicial 'Activo' en la API.", True
        )
        return

    member = ft.Dropdown(label="Socio", options=member_options, border_radius=10)
    branch = ft.Dropdown(label="Sede de retiro", options=branch_options, border_radius=10)
    copy = ft.Dropdown(label="Ejemplar disponible", options=copy_options, border_radius=10)
    start = text_input("Fecha de inicio", value=date.today().isoformat())
    due = text_input(
        "Fecha de vencimiento",
        value=(date.today() + timedelta(days=14)).isoformat(),
    )

    def submit() -> None:
        if not all(control.value for control in (member, branch, copy)):
            notify(app.page, "Seleccioná socio, sede y ejemplar.", True)
            return
        try:
            start_date = date.fromisoformat(start.value)
            due_date = date.fromisoformat(due.value)
            if due_date < start_date:
                notify(
                    app.page, "El vencimiento no puede ser anterior al inicio.", True
                )
                return
            app.api.request(
                "/api/prestamo-local",
                "POST",
                {
                    "fecha_inicio": start_date.isoformat(),
                    "fecha_vencimiento": due_date.isoformat(),
                    "fecha_devolucion": None,
                    "estado_prestamo_id": initial_state["id"],
                    "ejemplar_id": int(copy.value),
                    "multa_id": None,
                    "devolucion_id": None,
                    "sede_origen_id": int(branch.value),
                    "socio_id": int(member.value),
                },
            )
        except ValueError:
            notify(app.page, "Usá fechas válidas con formato AAAA-MM-DD.", True)
            return
        except ApiError as error:
            notify(app.page, str(error), True)
            return
        app.page.pop_dialog()
        notify(app.page, "Préstamo creado correctamente.")
        app.navigate("Préstamos")

    open_form(
        app.page,
        "Crear préstamo local",
        [member, branch, copy, start, due],
        submit,
    )
