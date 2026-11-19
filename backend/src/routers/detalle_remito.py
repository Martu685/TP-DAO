from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.auth import require_roles
from src.database import get_db
from src.library_rules import normalize
from src.models import (
    DetalleRemitoModel,
    EstadoRemitoModel,
    EjemplarModel,
    PrestamoInterbibliotecarioModel,
    RemitoModel,
)
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/detalle-remito",
    tags=["DetalleRemito"],
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)

class DetalleRemitoSchema(APIModel):
    remito_id: int
    ejemplar_id: int

class DetalleRemitoResponse(DetalleRemitoSchema):
    id: int

@router.post("", response_model=DetalleRemitoResponse, status_code=status.HTTP_201_CREATED)
def create_detalle_remito(detalle: DetalleRemitoSchema, db: Session = Depends(get_db)):
    remito = db.get(RemitoModel, detalle.remito_id)
    if remito is None:
        raise HTTPException(status_code=404, detail="Remito no encontrado")
    if db.get(EjemplarModel, detalle.ejemplar_id) is None:
        raise HTTPException(status_code=404, detail="Ejemplar no encontrado")
    remito_state = db.get(EstadoRemitoModel, remito.estado_remito_id)
    if remito_state is None or normalize(remito_state.descripcion) != "preparado":
        raise HTTPException(status_code=409, detail="Solo se agregan ejemplares a remitos Preparados")
    if not db.query(PrestamoInterbibliotecarioModel).filter(
        PrestamoInterbibliotecarioModel.remito_id == detalle.remito_id,
        PrestamoInterbibliotecarioModel.ejemplar_id == detalle.ejemplar_id,
    ).first():
        raise HTTPException(
            status_code=422,
            detail="El ejemplar debe pertenecer a un préstamo asociado al remito",
        )
    if db.query(DetalleRemitoModel).filter(
        DetalleRemitoModel.remito_id == detalle.remito_id,
        DetalleRemitoModel.ejemplar_id == detalle.ejemplar_id,
    ).first():
        raise HTTPException(status_code=409, detail="El ejemplar ya figura en el remito")
    db_detalle = DetalleRemitoModel(**detalle.model_dump())
    db.add(db_detalle)
    db.commit()
    db.refresh(db_detalle)
    return db_detalle

@router.get("", response_model=List[DetalleRemitoResponse])
def get_detalles_remito(
    remito_id: int | None = None,
    ejemplar_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DetalleRemitoModel)
    if remito_id is not None:
        query = query.filter(DetalleRemitoModel.remito_id == remito_id)
    if ejemplar_id is not None:
        query = query.filter(DetalleRemitoModel.ejemplar_id == ejemplar_id)
    return query.all()


@router.get("/{detalle_id}", response_model=DetalleRemitoResponse)
def get_detalle_remito(detalle_id: int, db: Session = Depends(get_db)):
    detalle = db.get(DetalleRemitoModel, detalle_id)
    if detalle is None:
        raise HTTPException(status_code=404, detail="Detalle de remito no encontrado")
    return detalle


@router.put("/{detalle_id}", response_model=DetalleRemitoResponse)
def update_detalle_remito(
    detalle_id: int,
    detalle_data: DetalleRemitoSchema,
    db: Session = Depends(get_db),
):
    detalle = db.get(DetalleRemitoModel, detalle_id)
    if detalle is None:
        raise HTTPException(status_code=404, detail="Detalle de remito no encontrado")
    raise HTTPException(
        status_code=422,
        detail="Los datos de un detalle no se pueden modificar; eliminelo y agreguelo nuevamente",
    )


@router.delete("/{detalle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_detalle_remito(detalle_id: int, db: Session = Depends(get_db)):
    detalle = db.get(DetalleRemitoModel, detalle_id)
    if detalle is None:
        raise HTTPException(status_code=404, detail="Detalle de remito no encontrado")

    remito = db.get(RemitoModel, detalle.remito_id)
    if remito is None:
        raise HTTPException(status_code=409, detail="El detalle tiene un remito inexistente")
    remito_state = db.get(EstadoRemitoModel, remito.estado_remito_id)
    if remito_state is None or normalize(remito_state.descripcion) != "preparado":
        raise HTTPException(
            status_code=409,
            detail="Solo se eliminan detalles de remitos Preparados",
        )

    db.delete(detalle)
    db.commit()
    return None
