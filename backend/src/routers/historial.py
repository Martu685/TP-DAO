from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import HistorialLecturaModel
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
):
    query = db.query(HistorialLecturaModel)
    if socio_id is not None:
        query = query.filter(HistorialLecturaModel.socio_id == socio_id)
    if libro_id is not None:
        query = query.filter(HistorialLecturaModel.libro_id == libro_id)
    return query.order_by(HistorialLecturaModel.fecha.desc()).all()