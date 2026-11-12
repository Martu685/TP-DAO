from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from src.database import get_db
from src.library_rules import (
    BusinessRuleError,
    get_status_by_id,
    get_status_by_name,
    is_exemplar_available,
    normalize,
    set_exemplar_state,
    validate_reservation,
)
from src.models import EstadoReservaModel, ReservaModel
from src.prestamo_observer import PrestamoEstadoEvent, prestamo_subject
from src.schemas import APIModel

router = APIRouter(prefix="/api/reserva", tags=["Reserva"])

class ReservaSchema(APIModel):
    fecha: date
    estado_reserva_id: int
    socio_id: int
    ejemplar_id: int
    sede_id: int

class ReservaResponse(ReservaSchema):
    id: int

@router.post("", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
def create_reserva(reserva: ReservaSchema, db: Session = Depends(get_db)):
    data = reserva.model_dump()
    try:
        exemplar = validate_reservation(
            db, data["socio_id"], data["sede_id"], data["ejemplar_id"]
        )
        state = get_status_by_id(db, EstadoReservaModel, data["estado_reserva_id"])
        if normalize(state.descripcion) != "pendiente":
            raise BusinessRuleError("Una reserva nueva debe comenzar Pendiente")
        ready_now = (
            exemplar.sede_id == data["sede_id"]
            and is_exemplar_available(db, exemplar)
        )
        if ready_now:
            state = get_status_by_name(db, EstadoReservaModel, "Disponible")
            set_exemplar_state(db, exemplar, "Reservado")
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    data["estado_reserva_id"] = state.id
    db_reserva = ReservaModel(**data)
    db.add(db_reserva)
    if ready_now:
        prestamo_subject.notify(
            PrestamoEstadoEvent(
                prestamo_id=None,
                estado_anterior="Pendiente",
                estado_nuevo="Disponible",
                socio_id=db_reserva.socio_id,
                mensaje=f"El ejemplar {exemplar.codigo} reservado está disponible para retirar.",
            ),
            db,
        )
    db.commit()
    db.refresh(db_reserva)
    return db_reserva

@router.get("", response_model=List[ReservaResponse])
def get_reservas(db: Session = Depends(get_db)):
    return db.query(ReservaModel).all()

@router.put("/{reserva_id}", response_model=ReservaResponse)
def update_reserva(reserva_id: int, reserva_data: ReservaSchema, db: Session = Depends(get_db)):
    db_reserva = db.query(ReservaModel).filter(ReservaModel.id == reserva_id).first()
    if not db_reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    data = reserva_data.model_dump()
    try:
        validate_reservation(
            db,
            data["socio_id"],
            data["sede_id"],
            data["ejemplar_id"],
            ignore_reservation_id=reserva_id,
        )
        current_state = get_status_by_id(
            db, EstadoReservaModel, db_reserva.estado_reserva_id
        )
        target_state = get_status_by_id(
            db, EstadoReservaModel, data["estado_reserva_id"]
        )
        current_name = normalize(current_state.descripcion)
        target_name = normalize(target_state.descripcion)
        if current_name != target_name and not (
            (current_name == "pendiente" and target_name == "cancelada")
            or (current_name == "disponible" and target_name == "cancelada")
        ):
            raise BusinessRuleError("La transición de estado de reserva no está permitida")
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    for key, value in data.items():
        setattr(db_reserva, key, value)
    db.commit()
    db.refresh(db_reserva)
    return db_reserva
