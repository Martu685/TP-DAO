from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from src.auth import require_roles
from src.database import get_db
from src.models import (
    EstadoPrestamoModel,
    EstadoRemitoModel,
    PrestamoInterbibliotecarioModel,
    RemitoModel,
)
from src.library_rules import (
    BusinessRuleError,
    get_status_by_id,
    normalize,
    set_exemplar_state,
    validate_interlibrary_loan,
    validate_loan_state_id,
)
from src.prestamo_state import InvalidPrestamoTransition
from src.prestamo_workflow import PrestamoStateNotFound, change_prestamo_state
from src.routers.prestamo import PrestamoBaseSchema

router = APIRouter(
    prefix="/api/prestamo-interbibliotecario",
    tags=["PrestamoInterbibliotecario"],
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)

# Subclase Pydantic que hereda de PrestamoBaseSchema
class PrestamoInterSchema(PrestamoBaseSchema):
    sede_origen_id: int
    sede_destino_id: int
    remito_id: Optional[int] = None

class PrestamoInterResponse(PrestamoInterSchema):
    id: int
    tipo_prestamo: str

@router.post("", response_model=PrestamoInterResponse, status_code=status.HTTP_201_CREATED)
def create_prestamo_inter(prestamo: PrestamoInterSchema, db: Session = Depends(get_db)):
    data = prestamo.model_dump()
    if any(data[key] is not None for key in ("fecha_devolucion", "multa_id", "devolucion_id")):
        raise HTTPException(
            status_code=422,
            detail="La devolución y la multa no se modifican al crear el préstamo",
        )
    try:
        exemplar = validate_interlibrary_loan(
            db,
            data["sede_origen_id"],
            data["sede_destino_id"],
            data["ejemplar_id"],
            data["fecha_inicio"],
            data["fecha_vencimiento"],
        )
        state = validate_loan_state_id(db, data["estado_prestamo_id"])
        if normalize(state.descripcion) != "pendiente":
            raise BusinessRuleError(
                "El préstamo interbibliotecario debe quedar Pendiente hasta despachar el remito"
            )
        if data["remito_id"] is not None:
            raise BusinessRuleError(
                "Asocie el remito después de crear el préstamo interbibliotecario"
            )
        set_exemplar_state(db, exemplar, "Reservado")
    except BusinessRuleError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    db_prestamo = PrestamoInterbibliotecarioModel(**data)
    db.add(db_prestamo)
    db.commit()
    db.refresh(db_prestamo)
    return db_prestamo

@router.get("", response_model=List[PrestamoInterResponse])
def get_prestamos_inter(db: Session = Depends(get_db)):
    return db.query(PrestamoInterbibliotecarioModel).all()

@router.put("/{prestamo_id}", response_model=PrestamoInterResponse)
def update_prestamo_inter(prestamo_id: int, prestamo_data: PrestamoInterSchema, db: Session = Depends(get_db)):
    db_prestamo = db.query(PrestamoInterbibliotecarioModel).filter(PrestamoInterbibliotecarioModel.id == prestamo_id).first()
    if not db_prestamo:
        raise HTTPException(status_code=404, detail="Préstamo interbibliotecario no encontrado")
    data = prestamo_data.model_dump()
    if any(
        data[key] != getattr(db_prestamo, key)
        for key in ("sede_origen_id", "sede_destino_id", "ejemplar_id", "remito_id")
    ):
        raise HTTPException(
            status_code=422,
            detail="No se pueden cambiar sedes, ejemplar ni remito de un préstamo existente",
        )
    if data["fecha_vencimiento"] < data["fecha_inicio"]:
        raise HTTPException(status_code=422, detail="El vencimiento no puede ser anterior al inicio")
    if data["fecha_inicio"] != db_prestamo.fecha_inicio or any(
        data[key] != getattr(db_prestamo, key)
        for key in ("fecha_devolucion", "multa_id", "devolucion_id")
    ):
        raise HTTPException(
            status_code=422,
            detail="Solo se puede modificar el vencimiento o el estado del préstamo",
        )
    target_state = get_status_by_id(db, EstadoPrestamoModel, data["estado_prestamo_id"])
    if normalize(target_state.descripcion) == "devuelto":
        raise HTTPException(
            status_code=422,
            detail="Use el endpoint de devolución para cerrar un préstamo",
        )
    if normalize(target_state.descripcion) == "activo":
        remito = db.get(RemitoModel, db_prestamo.remito_id) if db_prestamo.remito_id else None
        remito_state = db.get(EstadoRemitoModel, remito.estado_remito_id) if remito else None
        if remito_state is None or normalize(remito_state.descripcion) != "en transito":
            raise HTTPException(
                status_code=422,
                detail="El préstamo se activa únicamente al despachar un remito",
            )
    try:
        change_prestamo_state(db, db_prestamo, data["estado_prestamo_id"])
    except PrestamoStateNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (InvalidPrestamoTransition, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    db_prestamo.fecha_vencimiento = data["fecha_vencimiento"]
    db.commit()
    db.refresh(db_prestamo)
    return db_prestamo
