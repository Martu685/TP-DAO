from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from src.database import get_db
from src.models import MultaModel
from src.schemas import APIModel

router = APIRouter(prefix="/api/multa", tags=["Multa"])

class MultaSchema(APIModel):
    monto: float
    fecha: date
    motivo: str

class MultaResponse(MultaSchema):
    id: int

@router.post("", response_model=MultaResponse, status_code=status.HTTP_201_CREATED)
def create_multa(multa: MultaSchema, db: Session = Depends(get_db)):
    db_multa = MultaModel(**multa.model_dump())
    db.add(db_multa)
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
    db.delete(db_multa)
    db.commit()
    return None
