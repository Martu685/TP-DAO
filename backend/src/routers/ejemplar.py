from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from src.database import get_db
from src.models import EjemplarModel
from src.library_rules import (
    BusinessRuleError,
    get_status_by_id,
    has_open_loan,
    is_exemplar_available,
    require_active_branch,
)
from src.models import (
    DetalleRemitoModel,
    EstadoEjemplarModel,
    LibroModel,
    PrestamoModel,
    ReservaModel,
)
from src.schemas import APIModel

router = APIRouter(prefix="/api/ejemplar", tags=["Ejemplar"])

class EjemplarSchema(APIModel):
    codigo: str
    estado_fisico: str
    estado_ejemplar_id: int
    sede_id: int
    libro_id: int

class EjemplarResponse(EjemplarSchema):
    id: int

@router.post("", response_model=EjemplarResponse, status_code=status.HTTP_201_CREATED)
def create_ejemplar(ejemplar: EjemplarSchema, db: Session = Depends(get_db)):
    data = ejemplar.model_dump()
    try:
        require_active_branch(db, data["sede_id"])
        if db.get(LibroModel, data["libro_id"]) is None:
            raise BusinessRuleError("El libro no existe")
        state = get_status_by_id(db, EstadoEjemplarModel, data["estado_ejemplar_id"])
        if state.descripcion.strip().lower() not in {
            "disponible",
            "no disponible",
            "dañado",
            "danado",
            "extraviado",
            "destruido",
        }:
            raise BusinessRuleError("Un ejemplar nuevo no puede estar prestado o en tránsito")
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    db_ejemplar = EjemplarModel(**data)
    db.add(db_ejemplar)
    db.commit()
    db.refresh(db_ejemplar)
    return db_ejemplar

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

@router.put("/{ejemplar_id}", response_model=EjemplarResponse)
def update_ejemplar(ejemplar_id: int, ejemplar_data: EjemplarSchema, db: Session = Depends(get_db)):
    db_ejemplar = db.query(EjemplarModel).filter(EjemplarModel.id == ejemplar_id).first()
    if not db_ejemplar:
        raise HTTPException(status_code=404, detail="Ejemplar no encontrado")
    data = ejemplar_data.model_dump()
    if has_open_loan(db, ejemplar_id) and any(
        data[key] != getattr(db_ejemplar, key)
        for key in ("sede_id", "estado_ejemplar_id")
    ):
        raise HTTPException(
            status_code=409,
            detail="No se puede mover ni cambiar el estado de un ejemplar con préstamo abierto",
        )
    try:
        require_active_branch(db, data["sede_id"])
        get_status_by_id(db, EstadoEjemplarModel, data["estado_ejemplar_id"])
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    for key, value in data.items():
        setattr(db_ejemplar, key, value)
    db.commit()
    db.refresh(db_ejemplar)
    return db_ejemplar

@router.delete("/{ejemplar_id}", status_code=status.HTTP_204_NO_CONTENT)
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
