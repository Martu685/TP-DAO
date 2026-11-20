from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from pydantic import Field
from src.auth import require_roles
from src.database import get_db
from src.library_rules import (
    BusinessRuleError,
    get_status_by_name,
    normalize,
    require_active_branch,
)
from src.models import (
    DetalleRemitoModel,
    EstadoPrestamoModel,
    EstadoRemitoModel,
    IncidenciaRemitoModel,
    PrestamoInterbibliotecarioModel,
    RemitoModel,
)
from src.prestamo_workflow import change_prestamo_state
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/remito",
    tags=["Remito"],
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)

class RemitoResponse(APIModel):
    id: int
    numero: str
    fecha_emision: date
    fecha_recepcion: Optional[date] = None
    estado_remito_id: int

class RemitoCreate(APIModel):
    numero: str
    fecha_emision: date
    prestamos_inter_ids: List[int] = Field(default_factory=list)

class IncidenciaSchema(APIModel):
    descripcion: str

class IncidenciaResponse(IncidenciaSchema):
    id: int
    remito_id: int
    fecha: date
    resuelta: bool


def _get_remito(db: Session, remito_id: int):
    remito = db.get(RemitoModel, remito_id)
    if remito is None:
        raise HTTPException(status_code=404, detail="Remito no encontrado")
    return remito


def _get_remito_state(db: Session, remito):
    state = db.get(EstadoRemitoModel, remito.estado_remito_id)
    if state is None:
        raise HTTPException(status_code=409, detail="El remito tiene un estado inexistente")
    return state


@router.post("", response_model=RemitoResponse, status_code=status.HTTP_201_CREATED)
def create_remito(remito_data: RemitoCreate, db: Session = Depends(get_db)):
    if not remito_data.prestamos_inter_ids:
        raise HTTPException(
            status_code=422,
            detail="El remito debe incluir al menos un préstamo interbibliotecario",
        )
    if len(set(remito_data.prestamos_inter_ids)) != len(remito_data.prestamos_inter_ids):
        raise HTTPException(status_code=422, detail="Hay préstamos duplicados en el remito")
    if db.query(RemitoModel).filter(RemitoModel.numero == remito_data.numero).first():
        raise HTTPException(status_code=409, detail="Ya existe un remito con ese número")

    loans = [
        db.get(PrestamoInterbibliotecarioModel, loan_id)
        for loan_id in remito_data.prestamos_inter_ids
    ]
    if any(loan is None for loan in loans):
        raise HTTPException(status_code=404, detail="No existe uno de los préstamos indicados")
    routes = {(loan.sede_origen_id, loan.sede_destino_id) for loan in loans}
    if len(routes) != 1:
        raise HTTPException(
            status_code=422,
            detail="Todos los préstamos del remito deben compartir origen y destino",
        )

    for loan in loans:
        if loan.remito_id is not None:
            raise HTTPException(status_code=409, detail="Un préstamo ya está asociado a otro remito")
        loan_state = db.get(EstadoPrestamoModel, loan.estado_prestamo_id)
        if loan_state is None or normalize(loan_state.descripcion) != "pendiente":
            raise HTTPException(status_code=422, detail="Solo se pueden remitir préstamos Pendientes")

    try:
        prepared_state = get_status_by_name(db, EstadoRemitoModel, "Preparado")
    except BusinessRuleError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    remito = RemitoModel(
        numero=remito_data.numero,
        fecha_emision=remito_data.fecha_emision,
        estado_remito_id=prepared_state.id,
    )
    db.add(remito)
    db.flush()
    for loan in loans:
        loan.remito_id = remito.id
        db.add(DetalleRemitoModel(remito_id=remito.id, ejemplar_id=loan.ejemplar_id))
    db.commit()
    db.refresh(remito)
    return remito

@router.get("", response_model=List[RemitoResponse])
def get_remitos(db: Session = Depends(get_db)):
    return db.query(RemitoModel).all()


@router.get("/{remito_id}", response_model=RemitoResponse)
def get_remito(remito_id: int, db: Session = Depends(get_db)):
    return _get_remito(db, remito_id)


@router.post("/{remito_id}/despachar", response_model=RemitoResponse)
def dispatch_remito(remito_id: int, db: Session = Depends(get_db)):
    remito = _get_remito(db, remito_id)
    if normalize(_get_remito_state(db, remito).descripcion) != "preparado":
        raise HTTPException(status_code=409, detail="Solo se puede despachar un remito Preparado")
    loans = db.query(PrestamoInterbibliotecarioModel).filter(
        PrestamoInterbibliotecarioModel.remito_id == remito.id
    ).all()
    if not loans:
        raise HTTPException(status_code=409, detail="El remito no tiene préstamos asociados")
    try:
        transit_state = get_status_by_name(db, EstadoRemitoModel, "En tránsito")
        active_state = get_status_by_name(db, EstadoPrestamoModel, "Activo")
        for loan in loans:
            require_active_branch(db, loan.sede_origen_id)
            require_active_branch(db, loan.sede_destino_id)
            change_prestamo_state(db, loan, active_state.id)
        remito.estado_remito_id = transit_state.id
        db.commit()
        db.refresh(remito)
    except (BusinessRuleError, ValueError) as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    return remito


@router.post("/{remito_id}/cancelar", response_model=RemitoResponse)
def cancel_remito(remito_id: int, db: Session = Depends(get_db)):
    remito = _get_remito(db, remito_id)
    if normalize(_get_remito_state(db, remito).descripcion) != "preparado":
        raise HTTPException(
            status_code=409,
            detail="Solo se puede cancelar un remito Preparado",
        )
    try:
        cancelled_state = get_status_by_name(db, EstadoRemitoModel, "Cancelado")
        loans = db.query(PrestamoInterbibliotecarioModel).filter(
            PrestamoInterbibliotecarioModel.remito_id == remito.id
        ).all()
        for loan in loans:
            loan.remito_id = None
        remito.estado_remito_id = cancelled_state.id
        db.commit()
        db.refresh(remito)
    except BusinessRuleError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(error)) from error
    return remito


@router.post("/{remito_id}/recibir", response_model=RemitoResponse)
def receive_remito(remito_id: int, db: Session = Depends(get_db)):
    remito = _get_remito(db, remito_id)
    current_name = normalize(_get_remito_state(db, remito).descripcion)
    if current_name not in {"en transito", "incidencia"}:
        raise HTTPException(status_code=409, detail="Solo se puede recibir un remito en tránsito o con incidencia")
    if date.today() < remito.fecha_emision:
        raise HTTPException(status_code=422, detail="La recepción no puede preceder a la emisión")

    loans = db.query(PrestamoInterbibliotecarioModel).filter(
        PrestamoInterbibliotecarioModel.remito_id == remito.id
    ).all()
    if not loans:
        raise HTTPException(status_code=409, detail="El remito no tiene préstamos asociados")
    try:
        received_state = get_status_by_name(db, EstadoRemitoModel, "Recibido")
        for loan in loans:
            require_active_branch(db, loan.sede_destino_id)
            loan_state_name = normalize(loan.estado.descripcion)
            if loan_state_name not in {"activo", "vencido", "devuelto"}:
                raise BusinessRuleError(
                    "El préstamo asociado no está en un estado recepcionable"
                )
            loan.ejemplar.sede_id = loan.sede_destino_id
        remito.fecha_recepcion = date.today()
        remito.estado_remito_id = received_state.id
        db.commit()
        db.refresh(remito)
    except (BusinessRuleError, ValueError) as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    return remito


@router.post("/{remito_id}/incidencias", response_model=IncidenciaResponse, status_code=status.HTTP_201_CREATED)
def create_remito_incidence(remito_id: int, incidence_data: IncidenciaSchema, db: Session = Depends(get_db)):
    remito = _get_remito(db, remito_id)
    current_state = normalize(_get_remito_state(db, remito).descripcion)
    if current_state == "incidencia":
        raise HTTPException(
            status_code=409,
            detail="El remito ya tiene una incidencia registrada",
        )
    if current_state != "en transito":
        raise HTTPException(status_code=409, detail="Solo se registran incidencias durante el tránsito")
    try:
        incident_state = get_status_by_name(db, EstadoRemitoModel, "Incidencia")
    except BusinessRuleError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    incidence = IncidenciaRemitoModel(
        remito_id=remito.id,
        fecha=date.today(),
        descripcion=incidence_data.descripcion,
    )
    remito.estado_remito_id = incident_state.id
    db.add(incidence)
    db.commit()
    db.refresh(incidence)
    return incidence


@router.get("/{remito_id}/incidencias", response_model=List[IncidenciaResponse])
def get_remito_incidences(remito_id: int, db: Session = Depends(get_db)):
    _get_remito(db, remito_id)
    return db.query(IncidenciaRemitoModel).filter(
        IncidenciaRemitoModel.remito_id == remito_id
    ).all()
