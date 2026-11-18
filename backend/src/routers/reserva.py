from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from src.auth import get_current_user
from src.database import get_db
from src.library_rules import (
    BusinessRuleError,
    get_status_by_id,
    is_exemplar_available,
    normalize,
    release_exemplar_to_reservation,
    set_exemplar_state,
    validate_reservation,
)
from src.models import EstadoReservaModel, ReservaModel, UsuarioModel
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/reserva",
    tags=["Reserva"],
    dependencies=[Depends(get_current_user)],
)

class ReservaSchema(APIModel):
    fecha: date
    estado_reserva_id: int
    socio_id: int
    ejemplar_id: int
    sede_id: int

class ReservaResponse(ReservaSchema):
    id: int

@router.post("", response_model=ReservaResponse, status_code=status.HTTP_201_CREATED)
def create_reserva(
    reserva: ReservaSchema,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = reserva.model_dump()
    if current_user.rol == "socio" and data["socio_id"] != current_user.socio_id:
        raise HTTPException(status_code=403, detail="Solo podés reservar para tu propia cuenta")
    try:
        validate_reservation(
            db, data["socio_id"], data["sede_id"], data["ejemplar_id"]
        )
        state = get_status_by_id(db, EstadoReservaModel, data["estado_reserva_id"])
        if normalize(state.descripcion) != "pendiente":
            raise BusinessRuleError("Una reserva nueva debe comenzar Pendiente")
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    data["estado_reserva_id"] = state.id
    db_reserva = ReservaModel(**data)
    db.add(db_reserva)
    db.commit()
    db.refresh(db_reserva)
    return db_reserva

@router.get("", response_model=List[ReservaResponse])
def get_reservas(
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ReservaModel)
    if current_user.rol == "socio":
        query = query.filter(ReservaModel.socio_id == current_user.socio_id)
    return query.all()

@router.put("/{reserva_id}", response_model=ReservaResponse)
def update_reserva(
    reserva_id: int,
    reserva_data: ReservaSchema,
    current_user: UsuarioModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_reserva = db.query(ReservaModel).filter(ReservaModel.id == reserva_id).first()
    if not db_reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    data = reserva_data.model_dump()
    if current_user.rol == "socio" and db_reserva.socio_id != current_user.socio_id:
        raise HTTPException(status_code=403, detail="No podés modificar esta reserva")
    if any(
        data[key] != getattr(db_reserva, key)
        for key in ("fecha", "socio_id", "ejemplar_id", "sede_id")
    ):
        raise HTTPException(
            status_code=422,
            detail="No se pueden cambiar los datos de una reserva existente",
        )
    if current_user.rol == "socio":
        current_state = get_status_by_id(
            db, EstadoReservaModel, db_reserva.estado_reserva_id
        )
        target_state = get_status_by_id(
            db, EstadoReservaModel, data["estado_reserva_id"]
        )
        if (
            normalize(current_state.descripcion) != "aceptada"
            or normalize(target_state.descripcion) != "cancelada"
        ):
            raise HTTPException(
                status_code=403,
                detail="Solo podés cancelar una reserva Aceptada de tu cuenta",
            )
    try:
        current_state = get_status_by_id(
            db, EstadoReservaModel, db_reserva.estado_reserva_id
        )
        target_state = get_status_by_id(
            db, EstadoReservaModel, data["estado_reserva_id"]
        )
        current_name = normalize(current_state.descripcion)
        target_name = normalize(target_state.descripcion)
        allowed_transitions = {
            "pendiente": {"aceptada", "rechazada"},
            "aceptada": {"cancelada"},
        }
        if current_name != target_name and target_name not in allowed_transitions.get(
            current_name, set()
        ):
            raise BusinessRuleError("La transición de estado de reserva no está permitida")
        if target_name == "aceptada" and current_name == "pendiente":
            exemplar = db_reserva.ejemplar
            if exemplar.sede_id == data["sede_id"] and is_exemplar_available(db, exemplar):
                set_exemplar_state(db, exemplar, "Reservado")
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if current_name == "aceptada" and target_name == "cancelada":
        db_reserva.estado_reserva_id = target_state.id
        release_exemplar_to_reservation(db, db_reserva.ejemplar)
    for key, value in data.items():
        setattr(db_reserva, key, value)
    db.commit()
    db.refresh(db_reserva)
    return db_reserva
