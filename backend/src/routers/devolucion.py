import re
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
from src.prestamo_observer import PrestamoEstadoEvent, prestamo_subject
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


def _is_automatic_late_fine(fine: Optional[MultaModel]) -> bool:
    return fine is not None and re.fullmatch(
        r"devolucion tardia: \d+ dia\(s\)", normalize(fine.motivo)
    ) is not None


def _sync_automatic_late_fine(
    db: Session, loan: PrestamoLocalModel, return_date: date
) -> None:
    if MULTA_DIARIA < 0:
        raise HTTPException(status_code=500, detail="MULTA_DIARIA no puede ser negativa")

    fine = db.get(MultaModel, loan.multa_id) if loan.multa_id is not None else None
    if loan.multa_id is not None and fine is None:
        raise HTTPException(status_code=409, detail="La multa asociada no existe")

    is_automatic = _is_automatic_late_fine(fine)
    late_days = max(0, (return_date - loan.fecha_vencimiento).days)
    if late_days and MULTA_DIARIA:
        if fine is None:
            fine = MultaModel(
                monto=round(late_days * MULTA_DIARIA, 2),
                fecha=return_date,
                motivo=f"Devolución tardía: {late_days} día(s)",
            )
            db.add(fine)
            db.flush()
            loan.multa_id = fine.id
        elif is_automatic:
            fine.monto = round(late_days * MULTA_DIARIA, 2)
            fine.fecha = return_date
            fine.motivo = f"Devolución tardía: {late_days} día(s)"
    elif is_automatic:
        loan.multa_id = None
        db.flush()
        db.delete(fine)


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
        _sync_automatic_late_fine(db, loan, devolucion.fecha)

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

    loans = db.query(PrestamoModel).filter(PrestamoModel.devolucion_id == devolucion_id).all()
    if len(loans) > 1:
        raise HTTPException(
            status_code=409,
            detail="La devolución está asociada a más de un préstamo",
        )
    loan = loans[0] if loans else None
    if loan is not None:
        if not isinstance(loan, PrestamoLocalModel):
            raise HTTPException(
                status_code=409,
                detail="Solo se pueden editar devoluciones de préstamos locales",
            )
        if dev_data.fecha < loan.fecha_inicio or dev_data.fecha > date.today():
            raise HTTPException(
                status_code=422,
                detail="La fecha de devolución debe estar entre el inicio del préstamo y hoy",
            )
        _sync_automatic_late_fine(db, loan, dev_data.fecha)
        loan.fecha_devolucion = dev_data.fecha

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

    loans = db.query(PrestamoModel).filter(PrestamoModel.devolucion_id == devolucion_id).all()
    if len(loans) > 1:
        raise HTTPException(
            status_code=409,
            detail="La devolución está asociada a más de un préstamo",
        )
    loan = loans[0] if loans else None
    if loan is not None:
        if not isinstance(loan, PrestamoLocalModel):
            raise HTTPException(
                status_code=409,
                detail="Solo se pueden borrar devoluciones de préstamos locales",
            )
        try:
            target_name = "Vencido" if loan.fecha_vencimiento < date.today() else "Activo"
            target_state = get_status_by_name(db, EstadoPrestamoModel, target_name)
            current_state = db.get(EstadoPrestamoModel, loan.estado_prestamo_id)
            if current_state is None:
                raise BusinessRuleError("El estado actual del préstamo no existe")
        except BusinessRuleError as error:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from error

        fine = db.get(MultaModel, loan.multa_id) if loan.multa_id is not None else None
        if loan.multa_id is not None and fine is None:
            db.rollback()
            raise HTTPException(status_code=409, detail="La multa asociada no existe")
        try:
            set_exemplar_state(db, loan.ejemplar, "Prestado")
        except BusinessRuleError as error:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from error

        loan.devolucion_id = None
        loan.fecha_devolucion = None
        loan.estado_prestamo_id = target_state.id
        db.flush()
        if _is_automatic_late_fine(fine):
            loan.multa_id = None
            db.flush()
            db.delete(fine)
        prestamo_subject.notify(
            PrestamoEstadoEvent(
                prestamo_id=loan.id,
                estado_anterior=current_state.descripcion,
                estado_nuevo=target_state.descripcion,
                socio_id=loan.socio_id,
            ),
            db,
        )

    db.delete(db_dev)
    db.commit()
    return None
