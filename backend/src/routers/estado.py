from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from src.library_rules import normalize
from src.auth import get_current_user, require_roles
from src.database import get_db
from src.models import EstadoPrestamoModel, EstadoReservaModel, EstadoRemitoModel, EstadoEjemplarModel
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/estado",
    tags=["Estados Maestros"],
    dependencies=[Depends(get_current_user)],
)

class EstadoSchema(APIModel):
    descripcion: str

class EstadoResponse(EstadoSchema):
    id: int


def _create_state(db: Session, model, state: EstadoSchema, allowed_names):
    description = state.descripcion.strip()
    if normalize(description) not in allowed_names:
        raise HTTPException(
            status_code=422,
            detail=f"El estado '{description}' no pertenece al ciclo de vida configurado",
        )
    existing_states = db.query(model).all()
    if any(normalize(existing.descripcion) == normalize(description) for existing in existing_states):
        raise HTTPException(status_code=409, detail="El estado ya existe")
    db_est = model(descripcion=description)
    db.add(db_est)
    db.commit()
    db.refresh(db_est)
    return db_est


def _list_states(db: Session, model, allowed_names):
    return [
        state
        for state in db.query(model).all()
        if normalize(state.descripcion) in allowed_names
    ]


@router.get("/prestamo", response_model=List[EstadoResponse])
def get_estados_prestamo(db: Session = Depends(get_db)):
    return _list_states(
        db, EstadoPrestamoModel, {"pendiente", "activo", "vencido", "devuelto"}
    )

@router.post(
    "/prestamo",
    response_model=EstadoResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin"))],
)
def create_estado_prestamo(estado: EstadoSchema, db: Session = Depends(get_db)):
    return _create_state(
        db, EstadoPrestamoModel, estado, {"pendiente", "activo", "vencido", "devuelto"}
    )

@router.get("/reserva", response_model=List[EstadoResponse])
def get_estados_reserva(db: Session = Depends(get_db)):
    return _list_states(
        db,
        EstadoReservaModel,
        {"pendiente", "aceptada", "rechazada", "cancelada", "atendida"},
    )

@router.post(
    "/reserva",
    response_model=EstadoResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin"))],
)
def create_estado_reserva(estado: EstadoSchema, db: Session = Depends(get_db)):
    return _create_state(
        db,
        EstadoReservaModel,
        estado,
        {"pendiente", "aceptada", "rechazada", "cancelada", "atendida"},
    )

@router.get("/remito", response_model=List[EstadoResponse])
def get_estados_remito(db: Session = Depends(get_db)):
    return _list_states(
        db,
        EstadoRemitoModel,
        {"preparado", "en transito", "recibido", "incidencia", "cancelado"},
    )

@router.post(
    "/remito",
    response_model=EstadoResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin"))],
)
def create_estado_remito(estado: EstadoSchema, db: Session = Depends(get_db)):
    return _create_state(
        db,
        EstadoRemitoModel,
        estado,
        {"preparado", "en transito", "recibido", "incidencia", "cancelado"},
    )

@router.get("/ejemplar", response_model=List[EstadoResponse])
def get_estados_ejemplar(db: Session = Depends(get_db)):
    return _list_states(
        db, EstadoEjemplarModel, {"disponible", "prestado", "reservado"}
    )

@router.post(
    "/ejemplar",
    response_model=EstadoResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin"))],
)
def create_estado_ejemplar(estado: EstadoSchema, db: Session = Depends(get_db)):
    return _create_state(
        db, EstadoEjemplarModel, estado, {"disponible", "prestado", "reservado"}
    )
