import unicodedata

from sqlalchemy.orm import Session

from src.models import (
    EjemplarModel,
    EstadoEjemplarModel,
    EstadoPrestamoModel,
    EstadoReservaModel,
    PrestamoModel,
    PrestamoLocalModel,
    ReservaModel,
    SedeModel,
    SocioModel,
)
from src.prestamo_observer import PrestamoEstadoEvent, prestamo_subject


class BusinessRuleError(ValueError):
    pass


PHYSICAL_CONDITIONS = {
    "bueno": "Bueno",
    "danado": "Dañado",
    "extraviado": "Extraviado",
    "destruido": "Destruido",
}


def normalize(value):
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def validate_physical_condition(value):
    normalized = normalize(value)
    if normalized not in PHYSICAL_CONDITIONS:
        raise BusinessRuleError(
            "estado_fisico debe ser Bueno, Dañado, Extraviado o Destruido"
        )
    return PHYSICAL_CONDITIONS[normalized]


def get_status_by_name(db: Session, model, description):
    wanted = normalize(description)
    for state in db.query(model).all():
        if normalize(state.descripcion) == wanted:
            return state
    raise BusinessRuleError(f"No está configurado el estado '{description}'")


def get_status_by_id(db: Session, model, state_id):
    state = db.get(model, state_id)
    if state is None:
        raise BusinessRuleError("El estado indicado no existe")
    return state


def require_active_member(db: Session, member_id):
    member = db.get(SocioModel, member_id)
    if member is None:
        raise BusinessRuleError("El socio no existe")
    if not member.habilitado:
        raise BusinessRuleError("El socio está inhabilitado")
    return member


def require_active_branch(db: Session, branch_id):
    branch = db.get(SedeModel, branch_id)
    if branch is None:
        raise BusinessRuleError("La sede no existe")
    if not branch.activa:
        raise BusinessRuleError("La sede está dada de baja")
    return branch


def _loan_is_open(loan):
    if loan.fecha_devolucion is not None:
        return False
    state = loan.estado
    if state is None:
        return True
    return normalize(state.descripcion) not in {"devuelto", "cancelado", "finalizado"}


def is_exemplar_available(db: Session, exemplar, ignore_loan_id=None):
    item_state = db.get(EstadoEjemplarModel, exemplar.estado_ejemplar_id)
    if item_state is None or normalize(item_state.descripcion) != "disponible":
        return False
    if normalize(exemplar.estado_fisico) in {"extraviado", "destruido"}:
        return False

    return not has_open_loan(db, exemplar.id, ignore_loan_id)


def has_open_loan(db: Session, exemplar_id, ignore_loan_id=None):
    loans = db.query(PrestamoModel).filter(PrestamoModel.ejemplar_id == exemplar_id).all()
    return any(
        loan.id != ignore_loan_id and _loan_is_open(loan)
        for loan in loans
    )


def require_available_exemplar(db: Session, exemplar_id, ignore_loan_id=None):
    exemplar = db.get(EjemplarModel, exemplar_id)
    if exemplar is None:
        raise BusinessRuleError("El ejemplar no existe")
    if not is_exemplar_available(db, exemplar, ignore_loan_id):
        raise BusinessRuleError("El ejemplar no está disponible")
    return exemplar


def set_exemplar_state(db: Session, exemplar, description):
    exemplar.estado_ejemplar_id = get_status_by_name(
        db, EstadoEjemplarModel, description
    ).id


def release_exemplar_to_reservation(db: Session, exemplar, loan_id=None):
    set_exemplar_state(db, exemplar, "Disponible")
    reservations = db.query(ReservaModel).filter(
        ReservaModel.ejemplar_id == exemplar.id
    ).order_by(ReservaModel.fecha, ReservaModel.id).all()
    for reservation in reservations:
        state = db.get(EstadoReservaModel, reservation.estado_reserva_id)
        if (
            state
            and normalize(state.descripcion) in {"aceptada", "disponible"}
            and reservation.sede_id == exemplar.sede_id
            and normalize(exemplar.estado_fisico) not in {"extraviado", "destruido"}
        ):
            set_exemplar_state(db, exemplar, "Reservado")
            prestamo_subject.notify(
                PrestamoEstadoEvent(
                    prestamo_id=loan_id,
                    estado_anterior="Disponible",
                    estado_nuevo="Reservado",
                    socio_id=reservation.socio_id,
                    mensaje=f"El ejemplar {exemplar.codigo} reservado está disponible para retirar.",
                ),
                db,
            )
            return True
    return False


def validate_loan_dates(start_date, due_date):
    if due_date < start_date:
        raise BusinessRuleError("El vencimiento no puede ser anterior al inicio")


def validate_local_loan(
    db: Session,
    member_id,
    branch_id,
    exemplar_id,
    start_date,
    due_date,
    ignore_loan_id=None,
):
    require_active_member(db, member_id)
    require_active_branch(db, branch_id)
    validate_loan_dates(start_date, due_date)
    exemplar = db.get(EjemplarModel, exemplar_id)
    if exemplar is None:
        raise BusinessRuleError("El ejemplar no existe")
    if normalize(exemplar.estado_fisico) in {"extraviado", "destruido"}:
        raise BusinessRuleError("No se puede prestar un ejemplar Extraviado o Destruido")
    item_state = db.get(EstadoEjemplarModel, exemplar.estado_ejemplar_id)
    ready_reservation = find_ready_reservation(
        db, member_id, branch_id, exemplar_id
    )
    if has_open_loan(db, exemplar_id, ignore_loan_id) or not (
        (item_state and normalize(item_state.descripcion) == "disponible")
        or (
            item_state
            and normalize(item_state.descripcion) == "reservado"
            and ready_reservation
        )
    ):
        raise BusinessRuleError("El ejemplar no está disponible para este socio")
    if exemplar.sede_id != branch_id:
        raise BusinessRuleError("El ejemplar no pertenece a la sede de origen")
    member_loans = db.query(PrestamoLocalModel).filter(
        PrestamoLocalModel.socio_id == member_id
    ).all()
    if any(
        loan.id != ignore_loan_id
        and _loan_is_open(loan)
        and loan.ejemplar
        and loan.ejemplar.libro_id == exemplar.libro_id
        for loan in member_loans
    ):
        raise BusinessRuleError("El socio ya tiene un préstamo activo de este libro")
    return exemplar


def find_ready_reservation(db: Session, member_id, branch_id, exemplar_id):
    reservations = (
        db.query(ReservaModel)
        .filter(
            ReservaModel.sede_id == branch_id,
            ReservaModel.ejemplar_id == exemplar_id,
        )
        .order_by(ReservaModel.fecha, ReservaModel.id)
    )
    for reservation in reservations:
        state = db.get(EstadoReservaModel, reservation.estado_reserva_id)
        if state and normalize(state.descripcion) in {"aceptada", "disponible"}:
            return reservation if reservation.socio_id == member_id else None
    return None


def validate_interlibrary_loan(
    db: Session,
    origin_id,
    destination_id,
    exemplar_id,
    start_date,
    due_date,
    ignore_loan_id=None,
):
    origin = require_active_branch(db, origin_id)
    require_active_branch(db, destination_id)
    if origin.id == destination_id:
        raise BusinessRuleError("Las sedes de origen y destino deben ser distintas")
    validate_loan_dates(start_date, due_date)
    exemplar = require_available_exemplar(db, exemplar_id, ignore_loan_id)
    if normalize(exemplar.estado_fisico) in {"extraviado", "destruido"}:
        raise BusinessRuleError("No se puede prestar un ejemplar Extraviado o Destruido")
    if exemplar.sede_id != origin.id:
        raise BusinessRuleError("El ejemplar no está en la sede de origen")
    return exemplar


def validate_reservation(
    db: Session,
    member_id,
    branch_id,
    exemplar_id,
    ignore_reservation_id=None,
):
    require_active_member(db, member_id)
    require_active_branch(db, branch_id)
    exemplar = db.get(EjemplarModel, exemplar_id)
    if exemplar is None:
        raise BusinessRuleError("El ejemplar no existe")

    member_loans = db.query(PrestamoLocalModel).filter(
        PrestamoLocalModel.socio_id == member_id
    ).all()
    if any(
        _loan_is_open(loan)
        and loan.ejemplar
        and loan.ejemplar.libro_id == exemplar.libro_id
        for loan in member_loans
    ):
        raise BusinessRuleError("El socio ya tiene un préstamo activo de este libro")

    reservations = db.query(ReservaModel).filter(ReservaModel.socio_id == member_id)
    for reservation in reservations:
        if reservation.id == ignore_reservation_id:
            continue
        state = db.get(EstadoReservaModel, reservation.estado_reserva_id)
        same_book = (
            reservation.ejemplar
            and reservation.ejemplar.libro_id == exemplar.libro_id
        )
        if same_book and state and normalize(state.descripcion) not in {
            "atendida",
            "rechazada",
            "cancelada",
            "completada",
        }:
            raise BusinessRuleError(
                "El socio ya tiene una reserva activa para este libro"
            )
    return exemplar


def validate_loan_state_id(db: Session, state_id):
    return get_status_by_id(db, EstadoPrestamoModel, state_id)