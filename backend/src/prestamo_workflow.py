from datetime import date

from src.library_rules import (
    get_status_by_name,
    normalize,
    release_exemplar_to_reservation,
    set_exemplar_state,
)
from src.models import EstadoPrestamoModel
from src.prestamo_observer import PrestamoEstadoEvent, estado_subject
from src.prestamo_state import InvalidPrestamoTransition, validate_prestamo_transition


class PrestamoStateNotFound(LookupError):
    pass


def synchronize_overdue_loans(db, loans, today=None):
    current_date = today or date.today()
    overdue_state = None
    updated = False

    for loan in loans:
        if loan.fecha_devolucion is not None or loan.fecha_vencimiento >= current_date:
            continue

        current_state = db.get(EstadoPrestamoModel, loan.estado_prestamo_id)
        if current_state is None:
            raise PrestamoStateNotFound("El estado del préstamo no existe")
        if normalize(current_state.descripcion) not in {
            "activo",
            "en curso",
            "prestado",
        }:
            continue

        if overdue_state is None:
            overdue_state = get_status_by_name(db, EstadoPrestamoModel, "Vencido")
        change_prestamo_state(db, loan, overdue_state.id)
        updated = True

    return updated


def change_prestamo_state(
    db,
    prestamo,
    target_state_id,
    allow_return=False,
    release_copy=True,
):
    if prestamo.estado_prestamo_id == target_state_id:
        return

    current_state = db.get(EstadoPrestamoModel, prestamo.estado_prestamo_id)
    target_state = db.get(EstadoPrestamoModel, target_state_id)
    if current_state is None or target_state is None:
        raise PrestamoStateNotFound("El estado del préstamo no existe")

    validate_prestamo_transition(current_state.descripcion, target_state.descripcion)
    target_name = normalize(target_state.descripcion)
    if target_name == "devuelto" and not allow_return:
        raise InvalidPrestamoTransition(
            "Use el flujo de devolución para cerrar un préstamo"
        )

    prestamo.estado_prestamo_id = target_state.id
    if target_name == "activo":
        set_exemplar_state(db, prestamo.ejemplar, "Prestado")
    elif target_name == "devuelto" and release_copy:
        release_exemplar_to_reservation(db, prestamo.ejemplar, prestamo.id)
    elif target_name == "devuelto":
        set_exemplar_state(db, prestamo.ejemplar, "Disponible")

    estado_subject.notify(
        PrestamoEstadoEvent(
            prestamo_id=prestamo.id,
            estado_anterior=current_state.descripcion,
            estado_nuevo=target_state.descripcion,
            socio_id=getattr(prestamo, "socio_id", None),
        ),
        db,
    )