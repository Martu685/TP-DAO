from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import re
from src.auth import require_roles
from src.database import get_db
from src.models import NotificacionModel, ReservaModel, UsuarioModel
from src.schemas import APIModel

router = APIRouter(prefix="/api/notificacion", tags=["Notificacion"])

class NotificacionSchema(APIModel):
    fecha: datetime
    canal: str
    mensaje: str
    socio_id: int

class NotificacionResponse(NotificacionSchema):
    id: int

@router.post(
    "",
    response_model=NotificacionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def create_notificacion(notificacion: NotificacionSchema, db: Session = Depends(get_db)):
    db_notif = NotificacionModel(**notificacion.model_dump())
    db.add(db_notif)
    db.commit()
    db.refresh(db_notif)
    return db_notif

@router.get("", response_model=List[NotificacionResponse])
def get_notificaciones(
    socio_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(
        require_roles("socio", "bibliotecario", "admin")
    ),
):
    query = db.query(NotificacionModel)
    if current_user.rol == "socio":
        if current_user.socio_id is None:
            raise HTTPException(
                status_code=403,
                detail="La cuenta no está asociada a un socio",
            )
        if socio_id is not None and socio_id != current_user.socio_id:
            raise HTTPException(
                status_code=403,
                detail="No tenés permiso para consultar las notificaciones de otro socio",
            )
        query = query.filter(NotificacionModel.socio_id == current_user.socio_id)
    elif socio_id is not None:
        query = query.filter(NotificacionModel.socio_id == socio_id)
    notifications = query.order_by(NotificacionModel.fecha.desc()).all()
    result = []
    for notification in notifications:
        data = NotificacionResponse.model_validate(notification).model_dump()
        match = re.match(r"^(La reserva #\d+)( cambió de .+)$", notification.mensaje)
        if match:
            reservation_id = int(match.group(1).split("#", 1)[1])
            reservation = db.get(ReservaModel, reservation_id)
            exemplar = reservation.ejemplar if reservation else None
            book = exemplar.libro if exemplar else None
            if book is not None:
                data["mensaje"] = (
                    f"El libro «{book.titulo}» pasó de "
                    f"{match.group(2).removeprefix(' cambió de ')}"
                )
        result.append(data)
    return result
