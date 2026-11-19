from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import Field
from src.auth import get_current_user, require_roles
from src.database import get_db
from src.models import EjemplarModel
from src.library_rules import (
    BusinessRuleError,
    get_status_by_id,
    has_open_loan,
    is_exemplar_available,
    normalize,
    require_active_branch,
    validate_physical_condition,
)
from src.models import (
    DetalleRemitoModel,
    EstadoEjemplarModel,
    EstadoReservaModel,
    LibroModel,
    PrestamoModel,
    ReservaModel,
)
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/ejemplar",
    tags=["Ejemplar"],
    dependencies=[Depends(get_current_user)],
)

class EjemplarSchema(APIModel):
    codigo: str
    estado_fisico: str
    estado_ejemplar_id: int
    sede_id: int
    libro_id: int


class CrearEjemplaresSchema(EjemplarSchema):
    cantidad: int = Field(default=1, ge=1, le=500)

class EjemplarResponse(EjemplarSchema):
    id: int

@router.post(
    "",
    response_model=EjemplarResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def create_ejemplar(ejemplar: CrearEjemplaresSchema, db: Session = Depends(get_db)):
    data = ejemplar.model_dump()
    cantidad = data.pop("cantidad")
    try:
        require_active_branch(db, data["sede_id"])
        if db.get(LibroModel, data["libro_id"]) is None:
            raise BusinessRuleError("El libro no existe")
        data["estado_fisico"] = validate_physical_condition(data["estado_fisico"])
        state = get_status_by_id(db, EstadoEjemplarModel, data["estado_ejemplar_id"])
        if state.descripcion.strip().lower() != "disponible":
            raise BusinessRuleError("Un ejemplar nuevo debe estar Disponible")
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    base_code = data["codigo"].strip()
    codes = (
        [base_code]
        if cantidad == 1
        else [f"{base_code}-{number}" for number in range(1, cantidad + 1)]
    )
    existing_codes = {
        code
        for (code,) in db.query(EjemplarModel.codigo)
        .filter(EjemplarModel.codigo.in_(codes))
        .all()
    }
    if existing_codes:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un ejemplar con el código {sorted(existing_codes)[0]}",
        )
    db_ejemplares = [
        EjemplarModel(**{**data, "codigo": code}) for code in codes
    ]
    db.add_all(db_ejemplares)
    db.commit()
    db.refresh(db_ejemplares[0])
    return db_ejemplares[0]

@router.get("", response_model=List[EjemplarResponse])
def get_ejemplares(db: Session = Depends(get_db)):
    return db.query(EjemplarModel).all()


@router.get("/disponibilidad", response_model=List[EjemplarResponse])
def get_ejemplares_disponibles(
    libro_id: Optional[int] = None,
    sede_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    if sede_id is not None:
        try:
            require_active_branch(db, sede_id)
        except BusinessRuleError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    query = db.query(EjemplarModel)
    if libro_id is not None:
        query = query.filter(EjemplarModel.libro_id == libro_id)
    if sede_id is not None:
        query = query.filter(EjemplarModel.sede_id == sede_id)
    return [item for item in query.all() if is_exemplar_available(db, item)]

@router.put(
    "/{ejemplar_id}",
    response_model=EjemplarResponse,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def update_ejemplar(ejemplar_id: int, ejemplar_data: EjemplarSchema, db: Session = Depends(get_db)):
    db_ejemplar = db.query(EjemplarModel).filter(EjemplarModel.id == ejemplar_id).first()
    if not db_ejemplar:
        raise HTTPException(status_code=404, detail="Ejemplar no encontrado")
    data = ejemplar_data.model_dump()
    if has_open_loan(db, ejemplar_id) and any(
        data[key] != getattr(db_ejemplar, key)
        for key in ("sede_id", "estado_ejemplar_id", "estado_fisico")
    ):
        raise HTTPException(
            status_code=409,
            detail="No se puede modificar un ejemplar con préstamo abierto",
        )
    try:
        require_active_branch(db, data["sede_id"])
        data["estado_fisico"] = validate_physical_condition(data["estado_fisico"])
        target_state = get_status_by_id(db, EstadoEjemplarModel, data["estado_ejemplar_id"])
        current_state = get_status_by_id(db, EstadoEjemplarModel, db_ejemplar.estado_ejemplar_id)
        allowed_transitions = {
            "disponible": {"prestado", "reservado"},
            "prestado": {"disponible"},
            "reservado": {"prestado", "disponible"},
        }
        current_name = normalize(current_state.descripcion)
        target_name = normalize(target_state.descripcion)
        if current_name != target_name and target_name not in allowed_transitions.get(
            "prestado" if current_name == "en transito" else current_name, set()
        ):
            raise BusinessRuleError("La transición de estado del ejemplar no está permitida")
        if target_name == "prestado" and not has_open_loan(db, ejemplar_id):
            raise BusinessRuleError("Un ejemplar solo puede estar Prestado con un préstamo activo")
        active_reservations = db.query(ReservaModel).filter(
            ReservaModel.ejemplar_id == ejemplar_id
        ).all()
        has_accepted_reservation = any(
            (reservation_state := db.get(EstadoReservaModel, reservation.estado_reserva_id))
            and normalize(reservation_state.descripcion) in {"aceptada", "disponible"}
            for reservation in active_reservations
        )
        if target_name == "reservado" and not has_accepted_reservation:
            raise BusinessRuleError("Un ejemplar solo puede estar Reservado con una reserva Aceptada")
        if target_name == "disponible" and (
            has_open_loan(db, ejemplar_id) or has_accepted_reservation
        ):
            raise BusinessRuleError("El ejemplar todavía tiene un préstamo o reserva activa")
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    for key, value in data.items():
        setattr(db_ejemplar, key, value)
    db.commit()
    db.refresh(db_ejemplar)
    return db_ejemplar

@router.delete(
    "/{ejemplar_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def delete_ejemplar(ejemplar_id: int, db: Session = Depends(get_db)):
    db_ejemplar = db.query(EjemplarModel).filter(EjemplarModel.id == ejemplar_id).first()
    if not db_ejemplar:
        raise HTTPException(status_code=404, detail="Ejemplar no encontrado")
    has_history = any(
        (
            db.query(PrestamoModel).filter(PrestamoModel.ejemplar_id == ejemplar_id).first(),
            db.query(ReservaModel).filter(ReservaModel.ejemplar_id == ejemplar_id).first(),
            db.query(DetalleRemitoModel).filter(DetalleRemitoModel.ejemplar_id == ejemplar_id).first(),
        )
    )
    if has_history:
        raise HTTPException(
            status_code=409,
            detail="No se puede borrar un ejemplar con préstamos, reservas o remitos asociados",
        )
    db.delete(db_ejemplar)
    db.commit()
    return None
