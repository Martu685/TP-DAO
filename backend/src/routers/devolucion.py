from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from src.config import MULTA_DIARIA
from src.database import get_db
from src.library_rules import (
    BusinessRuleError,
    get_status_by_name,
    normalize,
    release_exemplar_to_reservation,
    set_exemplar_state,
)
from src.models import (
    DevolucionModel,
    EstadoPrestamoModel,
    HistorialLecturaModel,
    MultaModel,
    PrestamoLocalModel,
    PrestamoModel,
)
from src.prestamo_workflow import change_prestamo_state
from src.schemas import APIModel

router = APIRouter(prefix="/api/devolucion", tags=["Devolucion"])

class DevolucionSchema(APIModel):
    fecha: date
    observaciones: Optional[str] = None

class DevolucionResponse(DevolucionSchema):
    id: int

class LoanReturnRequest(DevolucionSchema):
    estado_fisico: str = "Bueno"

class DevolucionCreateRequest(LoanReturnRequest):
    prestamo_id: int

@router.post("", response_model=DevolucionResponse, status_code=status.HTTP_201_CREATED)
def create_devolucion(devolucion: DevolucionCreateRequest, db: Session = Depends(get_db)):
    return return_loan(devolucion.prestamo_id, devolucion, db)

@router.get("", response_model=List[DevolucionResponse])
def get_devoluciones(db: Session = Depends(get_db)):
    return db.query(DevolucionModel).all()


@router.post("/prestamo/{prestamo_id}", response_model=DevolucionResponse, status_code=status.HTTP_201_CREATED)
def return_loan(
    prestamo_id: int,
    devolucion: LoanReturnRequest,
    db: Session = Depends(get_db),
):
    loan = db.get(PrestamoModel, prestamo_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    if not isinstance(loan, PrestamoLocalModel):
        raise HTTPException(
            status_code=422,
            detail="Los préstamos interbibliotecarios se completan al recibir su remito",
        )
    if loan.fecha_devolucion is not None:
        raise HTTPException(status_code=409, detail="El préstamo ya fue devuelto")
    if devolucion.fecha < loan.fecha_inicio or devolucion.fecha > date.today():
        raise HTTPException(
            status_code=422,
            detail="La fecha de devolución debe estar entre el inicio del préstamo y hoy",
        )
    if MULTA_DIARIA < 0:
        raise HTTPException(status_code=500, detail="MULTA_DIARIA no puede ser negativa")

    physical_condition = normalize(devolucion.estado_fisico)
    physical_states = {
        "bueno": ("Disponible", "Bueno"),
        "regular": ("Disponible", "Regular"),
        "disponible": ("Disponible", "Bueno"),
        "danado": ("Dañado", "Dañado"),
        "extraviado": ("Extraviado", "Extraviado"),
        "destruido": ("Destruido", "Destruido"),
    }
    if physical_condition not in physical_states:
        raise HTTPException(
            status_code=422,
            detail="estado_fisico debe ser Bueno, Regular, Dañado, Extraviado o Destruido",
        )

    try:
        returned_state = get_status_by_name(db, EstadoPrestamoModel, "Devuelto")
        return_record = DevolucionModel(
            fecha=devolucion.fecha,
            observaciones=devolucion.observaciones,
        )
        db.add(return_record)
        db.flush()
        loan.devolucion_id = return_record.id
        loan.fecha_devolucion = devolucion.fecha

        late_days = max(0, (devolucion.fecha - loan.fecha_vencimiento).days)
        if late_days and MULTA_DIARIA:
            fine = MultaModel(
                monto=round(late_days * MULTA_DIARIA, 2),
                fecha=devolucion.fecha,
                motivo=f"Devolución tardía: {late_days} día(s)",
            )
            db.add(fine)
            db.flush()
            loan.multa_id = fine.id

        change_prestamo_state(
            db, loan, returned_state.id, allow_return=True, release_copy=False
        )
        item_state, normalized_condition = physical_states[physical_condition]
        loan.ejemplar.estado_fisico = normalized_condition
        set_exemplar_state(db, loan.ejemplar, item_state)

        db.add(
            HistorialLecturaModel(
                fecha=devolucion.fecha,
                socio_id=loan.socio_id,
                libro_id=loan.ejemplar.libro_id,
                prestamo_id=loan.id,
            )
        )

        if item_state == "Disponible":
            release_exemplar_to_reservation(db, loan.ejemplar, loan.id)

        db.commit()
        db.refresh(return_record)
    except (BusinessRuleError, ValueError) as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    return return_record

@router.put("/{devolucion_id}", response_model=DevolucionResponse)
def update_devolucion(devolucion_id: int, dev_data: DevolucionSchema, db: Session = Depends(get_db)):
    db_dev = db.query(DevolucionModel).filter(DevolucionModel.id == devolucion_id).first()
    if not db_dev:
        raise HTTPException(status_code=404, detail="Devolución no encontrada")
    if db.query(PrestamoModel).filter(PrestamoModel.devolucion_id == devolucion_id).first():
        raise HTTPException(
            status_code=409,
            detail="No se puede editar una devolución que cerró un préstamo",
        )
    for key, value in dev_data.model_dump().items():
        setattr(db_dev, key, value)
    db.commit()
    db.refresh(db_dev)
    return db_dev

@router.delete("/{devolucion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_devolucion(devolucion_id: int, db: Session = Depends(get_db)):
    db_dev = db.query(DevolucionModel).filter(DevolucionModel.id == devolucion_id).first()
    if not db_dev:
        raise HTTPException(status_code=404, detail="Devolución no encontrada")
    if db.query(PrestamoModel).filter(PrestamoModel.devolucion_id == devolucion_id).first():
        raise HTTPException(
            status_code=409,
            detail="No se puede borrar una devolución que cerró un préstamo",
        )
    db.delete(db_dev)
    db.commit()
    return None
