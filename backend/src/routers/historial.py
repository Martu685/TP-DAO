from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth import require_roles
from src.database import get_db
from src.models import HistorialLecturaModel, UsuarioModel
from src.schemas import APIModel


router = APIRouter(prefix="/api/historial-lecturas", tags=["Historial de lecturas"])


class HistorialLecturaResponse(APIModel):
    id: int
    fecha: date
    socio_id: int
    libro_id: int
    prestamo_id: Optional[int] = None


@router.get("", response_model=List[HistorialLecturaResponse])
def get_historial_lecturas(
    socio_id: Optional[int] = None,
    libro_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: UsuarioModel = Depends(
        require_roles("socio", "bibliotecario", "admin")
    ),
):
    query = db.query(HistorialLecturaModel)
    if current_user.rol == "socio":
        if current_user.socio_id is None:
            raise HTTPException(
                status_code=403,
                detail="La cuenta no está asociada a un socio",
            )
        if socio_id is not None and socio_id != current_user.socio_id:
            raise HTTPException(
                status_code=403,
                detail="No tenés permiso para consultar el historial de otro socio",
            )
        query = query.filter(
            HistorialLecturaModel.socio_id == current_user.socio_id
        )
    elif socio_id is not None:
        query = query.filter(HistorialLecturaModel.socio_id == socio_id)
    if libro_id is not None:
        query = query.filter(HistorialLecturaModel.libro_id == libro_id)
    return query.order_by(HistorialLecturaModel.fecha.desc()).all()