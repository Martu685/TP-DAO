from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.auth import require_roles
from src.database import get_db
from src.models import (
    EstadoPrestamoModel,
    EstadoReservaModel,
    PrestamoLocalModel,
    UsuarioModel,
)
from src.library_rules import (
    BusinessRuleError,
    find_ready_reservation,
    get_status_by_id,
    get_status_by_name,
    normalize,
    set_exemplar_state,
    validate_local_loan,
    validate_loan_state_id,
)
from src.prestamo_state import InvalidPrestamoTransition, validate_initial_prestamo_state
from src.prestamo_observer import notify_reservation_state_change
from src.prestamo_workflow import PrestamoStateNotFound, change_prestamo_state
from src.routers.prestamo import PrestamoBaseSchema

router = APIRouter(
    prefix="/api/prestamo-local",
    tags=["PrestamoLocal"],
)

# Subclase Pydantic que hereda de PrestamoBaseSchema
class PrestamoLocalSchema(PrestamoBaseSchema):
    sede_origen_id: int
    socio_id: int

class PrestamoLocalResponse(PrestamoLocalSchema):
    id: int
    tipo_prestamo: str

@router.post(
    "",
    response_model=PrestamoLocalResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def create_prestamo_local(prestamo: PrestamoLocalSchema, db: Session = Depends(get_db)):
    data = prestamo.model_dump()
    if any(data[key] is not None for key in ("fecha_devolucion", "multa_id", "devolucion_id")):
        raise HTTPException(
            status_code=422,
            detail="La devolución y la multa se generan desde el flujo de devolución",
        )
    try:
        exemplar = validate_local_loan(
            db,
            data["socio_id"],
            data["sede_origen_id"],
            data["ejemplar_id"],
            data["fecha_inicio"],
            data["fecha_vencimiento"],
        )
        state = validate_loan_state_id(db, data["estado_prestamo_id"])
        validate_initial_prestamo_state(state.descripcion)
        ready_reservation = find_ready_reservation(
            db, data["socio_id"], data["sede_origen_id"], data["ejemplar_id"]
        )
        if ready_reservation:
            reservation_state = get_status_by_id(
                db, EstadoReservaModel, ready_reservation.estado_reserva_id
            )
            attended_state = get_status_by_name(
                db, EstadoReservaModel, "Atendida"
            )
            ready_reservation.estado_reserva_id = attended_state.id
            notify_reservation_state_change(
                ready_reservation,
                reservation_state.descripcion,
                attended_state.descripcion,
                db,
            )
        set_exemplar_state(db, exemplar, "Prestado")
    except (BusinessRuleError, InvalidPrestamoTransition) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    db_prestamo = PrestamoLocalModel(**data)
    db.add(db_prestamo)
    db.commit()
    db.refresh(db_prestamo)
    return db_prestamo

@router.get("", response_model=List[PrestamoLocalResponse])
def get_prestamos_locales(
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(
        require_roles("socio", "bibliotecario", "admin")
    ),
):
    query = db.query(PrestamoLocalModel)
    if current_user.rol == "socio":
        if current_user.socio_id is None:
            raise HTTPException(
                status_code=403,
                detail="La cuenta no está asociada a un socio",
            )
        query = query.filter(PrestamoLocalModel.socio_id == current_user.socio_id)
    return query.all()

@router.put(
    "/{prestamo_id}",
    response_model=PrestamoLocalResponse,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def update_prestamo_local(prestamo_id: int, prestamo_data: PrestamoLocalSchema, db: Session = Depends(get_db)):
    db_prestamo = db.query(PrestamoLocalModel).filter(PrestamoLocalModel.id == prestamo_id).first()
    if not db_prestamo:
        raise HTTPException(status_code=404, detail="Préstamo local no encontrado")
    data = prestamo_data.model_dump()
    if any(
        data[key] != getattr(db_prestamo, key)
        for key in ("socio_id", "sede_origen_id", "ejemplar_id")
    ):
        raise HTTPException(
            status_code=422,
            detail="No se pueden cambiar socio, sede ni ejemplar de un préstamo existente",
        )
    if data["fecha_vencimiento"] < data["fecha_inicio"]:
        raise HTTPException(status_code=422, detail="El vencimiento no puede ser anterior al inicio")
    if data["fecha_inicio"] != db_prestamo.fecha_inicio or any(
        data[key] != getattr(db_prestamo, key)
        for key in ("fecha_devolucion", "multa_id", "devolucion_id")
    ):
        raise HTTPException(
            status_code=422,
            detail="Solo se puede modificar el vencimiento o el estado del préstamo",
        )
    target_state = get_status_by_id(
        db, EstadoPrestamoModel, data["estado_prestamo_id"]
    )
    if normalize(target_state.descripcion) == "devuelto":
        raise HTTPException(
            status_code=422,
            detail="Use el endpoint de devolución para cerrar un préstamo",
        )
    try:
        change_prestamo_state(db, db_prestamo, data["estado_prestamo_id"])
    except PrestamoStateNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (InvalidPrestamoTransition, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    db_prestamo.fecha_vencimiento = data["fecha_vencimiento"]
    db.commit()
    db.refresh(db_prestamo)
    return db_prestamo
