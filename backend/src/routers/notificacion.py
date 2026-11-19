from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from src.auth import require_roles
from src.database import get_db
from src.models import NotificacionModel, SocioModel
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/notificacion",
    tags=["Notificacion"],
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)

class NotificacionSchema(APIModel):
    fecha: datetime
    canal: str
    mensaje: str
    socio_id: int

class NotificacionResponse(NotificacionSchema):
    id: int

@router.post("", response_model=NotificacionResponse, status_code=status.HTTP_201_CREATED)
def create_notificacion(notificacion: NotificacionSchema, db: Session = Depends(get_db)):
    socio = db.get(SocioModel, notificacion.socio_id)
    if socio is None:
        raise HTTPException(status_code=404, detail="Socio no encontrado")
    if not notificacion.canal.strip():
        raise HTTPException(status_code=422, detail="El canal no puede estar vacío")
    if not notificacion.mensaje.strip():
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío")

    db_notif = NotificacionModel(**notificacion.model_dump())
    db.add(db_notif)
    db.commit()
    db.refresh(db_notif)
    return db_notif

@router.get("", response_model=List[NotificacionResponse])
def get_notificaciones(
    socio_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(NotificacionModel)
    if socio_id is not None:
        query = query.filter(NotificacionModel.socio_id == socio_id)
    return query.order_by(NotificacionModel.fecha.desc()).all()
