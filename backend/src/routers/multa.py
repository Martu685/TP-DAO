from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from src.auth import require_roles
from src.database import get_db
from src.models import MultaModel, PrestamoModel
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/multa",
    tags=["Multa"],
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)

class MultaSchema(APIModel):
    monto: float
    fecha: date
    motivo: str

class MultaResponse(MultaSchema):
    id: int

class MultaCreateRequest(MultaSchema):
    prestamo_id: Optional[int] = None

@router.post("", response_model=MultaResponse, status_code=status.HTTP_201_CREATED)
def create_multa(multa: MultaCreateRequest, db: Session = Depends(get_db)):
    loan = None
    if multa.prestamo_id is not None:
        loan = db.get(PrestamoModel, multa.prestamo_id)
        if loan is None:
            raise HTTPException(status_code=404, detail="Préstamo no encontrado")
        if loan.multa_id is not None:
            raise HTTPException(
                status_code=409,
                detail="El préstamo ya tiene una multa asociada",
            )

    db_multa_data = multa.model_dump(exclude={"prestamo_id"})
    db_multa = MultaModel(**db_multa_data)
    db.add(db_multa)
    if loan is not None:
        db.flush()
        loan.multa_id = db_multa.id
    db.commit()
    db.refresh(db_multa)
    return db_multa

@router.get("", response_model=List[MultaResponse])
def get_multas(db: Session = Depends(get_db)):
    return db.query(MultaModel).all()

@router.put("/{multa_id}", response_model=MultaResponse)
def update_multa(multa_id: int, multa_data: MultaSchema, db: Session = Depends(get_db)):
    db_multa = db.query(MultaModel).filter(MultaModel.id == multa_id).first()
    if not db_multa:
        raise HTTPException(status_code=404, detail="Multa no encontrada")
    for key, value in multa_data.model_dump().items():
        setattr(db_multa, key, value)
    db.commit()
    db.refresh(db_multa)
    return db_multa

@router.delete("/{multa_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_multa(multa_id: int, db: Session = Depends(get_db)):
    db_multa = db.query(MultaModel).filter(MultaModel.id == multa_id).first()
    if not db_multa:
        raise HTTPException(status_code=404, detail="Multa no encontrada")
    loans = db.query(PrestamoModel).filter(PrestamoModel.multa_id == multa_id).all()
    for loan in loans:
        loan.multa_id = None
    if loans:
        db.flush()
    db.delete(db_multa)
    db.commit()
    return None
