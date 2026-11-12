from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.database import get_db
from src.models import SocioModel
from src.schemas import APIModel

router = APIRouter(prefix="/api/socio", tags=["Socio"])

class SocioSchema(APIModel):
    nombre: str
    apellido: str
    dni: int
    email: str
    telefono: str
    habilitado: bool = True

class SocioResponse(SocioSchema):
    id: int

@router.post("", response_model=SocioResponse, status_code=status.HTTP_201_CREATED)
def create_socio(socio: SocioSchema, db: Session = Depends(get_db)):
    db_socio = SocioModel(**socio.model_dump())
    db.add(db_socio)
    db.commit()
    db.refresh(db_socio)
    return db_socio

@router.get("", response_model=List[SocioResponse])
def get_socios(db: Session = Depends(get_db)):
    return db.query(SocioModel).all()

@router.put("/{socio_id}", response_model=SocioResponse)
def update_socio(socio_id: int, socio_data: SocioSchema, db: Session = Depends(get_db)):
    db_socio = db.query(SocioModel).filter(SocioModel.id == socio_id).first()
    if not db_socio:
        raise HTTPException(status_code=404, detail="Socio no encontrado")
    for key, value in socio_data.model_dump().items():
        setattr(db_socio, key, value)
    db.commit()
    db.refresh(db_socio)
    return db_socio

@router.delete("/{socio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_socio(socio_id: int, db: Session = Depends(get_db)):
    db_socio = db.query(SocioModel).filter(SocioModel.id == socio_id).first()
    if not db_socio:
        raise HTTPException(status_code=404, detail="Socio no encontrado")
    db_socio.habilitado = False
    db.commit()
    return None
