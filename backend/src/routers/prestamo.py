from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from src.auth import require_roles
from src.database import get_db
from src.models import PrestamoModel
from src.prestamo_workflow import synchronize_overdue_loans
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/prestamo",
    tags=["Prestamo (Base)"],
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)

# Clase Base Pydantic con los atributos comunes del UML
class PrestamoBaseSchema(APIModel):
    fecha_inicio: date
    fecha_vencimiento: date
    fecha_devolucion: Optional[date] = None
    estado_prestamo_id: int
    ejemplar_id: int
    multa_id: Optional[int] = None
    devolucion_id: Optional[int] = None

class PrestamoResponse(PrestamoBaseSchema):
    id: int
    tipo_prestamo: str

@router.get("", response_model=List[PrestamoResponse])
def get_prestamos(db: Session = Depends(get_db)):
    """
    Consulta polimórfica general: retorna todos los préstamos 
    (Locales e Interbibliotecarios) aprovechando la herencia de la BD.
    """
    loans = db.query(PrestamoModel).all()
    if synchronize_overdue_loans(db, loans):
        db.commit()
    return loans

@router.get("/{prestamo_id}", response_model=PrestamoResponse)
def get_prestamo_by_id(prestamo_id: int, db: Session = Depends(get_db)):
    prestamo = db.query(PrestamoModel).filter(PrestamoModel.id == prestamo_id).first()
    if not prestamo:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    if synchronize_overdue_loans(db, [prestamo]):
        db.commit()
    return prestamo
