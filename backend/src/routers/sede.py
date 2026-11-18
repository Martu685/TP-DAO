from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.auth import get_current_user, require_roles
from src.database import get_db
from src.models import SedeModel
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/sede",
    tags=["Sede"],
    dependencies=[Depends(get_current_user)],
)

class SedeSchema(APIModel):
    nombre: str
    direccion: str
    email: str
    horarios: str
    activa: bool = True

class SedeResponse(SedeSchema):
    id: int

@router.post(
    "",
    response_model=SedeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def create_sede(sede: SedeSchema, db: Session = Depends(get_db)):
    db_sede = SedeModel(**sede.model_dump())
    db.add(db_sede)
    db.commit()
    db.refresh(db_sede)
    return db_sede

@router.get("", response_model=List[SedeResponse])
def get_sedes(db: Session = Depends(get_db)):
    return db.query(SedeModel).all()

@router.put(
    "/{sede_id}",
    response_model=SedeResponse,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def update_sede(sede_id: int, sede_data: SedeSchema, db: Session = Depends(get_db)):
    db_sede = db.query(SedeModel).filter(SedeModel.id == sede_id).first()
    if not db_sede:
        raise HTTPException(status_code=404, detail="Sede no encontrada")
    for key, value in sede_data.model_dump().items():
        setattr(db_sede, key, value)
    db.commit()
    db.refresh(db_sede)
    return db_sede

@router.delete(
    "/{sede_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def delete_sede(sede_id: int, db: Session = Depends(get_db)):
    db_sede = db.query(SedeModel).filter(SedeModel.id == sede_id).first()
    if not db_sede:
        raise HTTPException(status_code=404, detail="Sede no encontrada")
    db_sede.activa = False
    db.commit()
    return None
