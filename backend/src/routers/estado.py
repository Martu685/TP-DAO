from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from src.database import get_db
from src.models import EstadoPrestamoModel, EstadoReservaModel, EstadoRemitoModel, EstadoEjemplarModel
from src.schemas import APIModel

router = APIRouter(prefix="/api/estado", tags=["Estados Maestros"])

class EstadoSchema(APIModel):
    descripcion: str

class EstadoResponse(EstadoSchema):
    id: int

@router.get("/prestamo", response_model=List[EstadoResponse])
def get_estados_prestamo(db: Session = Depends(get_db)):
    return db.query(EstadoPrestamoModel).all()

@router.post("/prestamo", response_model=EstadoResponse, status_code=status.HTTP_201_CREATED)
def create_estado_prestamo(estado: EstadoSchema, db: Session = Depends(get_db)):
    db_est = EstadoPrestamoModel(**estado.model_dump())
    db.add(db_est)
    db.commit()
    db.refresh(db_est)
    return db_est

@router.get("/reserva", response_model=List[EstadoResponse])
def get_estados_reserva(db: Session = Depends(get_db)):
    return db.query(EstadoReservaModel).all()

@router.post("/reserva", response_model=EstadoResponse, status_code=status.HTTP_201_CREATED)
def create_estado_reserva(estado: EstadoSchema, db: Session = Depends(get_db)):
    db_est = EstadoReservaModel(**estado.model_dump())
    db.add(db_est)
    db.commit()
    db.refresh(db_est)
    return db_est

@router.get("/remito", response_model=List[EstadoResponse])
def get_estados_remito(db: Session = Depends(get_db)):
    return db.query(EstadoRemitoModel).all()

@router.post("/remito", response_model=EstadoResponse, status_code=status.HTTP_201_CREATED)
def create_estado_remito(estado: EstadoSchema, db: Session = Depends(get_db)):
    db_est = EstadoRemitoModel(**estado.model_dump())
    db.add(db_est)
    db.commit()
    db.refresh(db_est)
    return db_est

@router.get("/ejemplar", response_model=List[EstadoResponse])
def get_estados_ejemplar(db: Session = Depends(get_db)):
    return db.query(EstadoEjemplarModel).all()

@router.post("/ejemplar", response_model=EstadoResponse, status_code=status.HTTP_201_CREATED)
def create_estado_ejemplar(estado: EstadoSchema, db: Session = Depends(get_db)):
    db_est = EstadoEjemplarModel(**estado.model_dump())
    db.add(db_est)
    db.commit()
    db.refresh(db_est)
    return db_est
