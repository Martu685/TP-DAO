from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth import require_roles
from src.database import get_db
from src.library_rules import is_exemplar_available, normalize
from src.models import (
    EstadoReservaModel,
    EstadoRemitoModel,
    DetalleRemitoModel,
    EjemplarModel,
    IncidenciaRemitoModel,
    LibroModel,
    MultaModel,
    PrestamoModel,
    PrestamoInterbibliotecarioModel,
    RemitoModel,
    ReservaModel,
    SedeModel,
)


router = APIRouter(
    prefix="/api/reportes",
    tags=["Reportes"],
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)


def _loan_report_row(loan):
    return {
        "prestamo_id": loan.id,
        "tipo": loan.tipo_prestamo,
        "ejemplar_id": loan.ejemplar_id,
        "codigo_ejemplar": loan.ejemplar.codigo if loan.ejemplar else None,
        "libro_id": loan.ejemplar.libro_id if loan.ejemplar else None,
        "titulo": loan.ejemplar.libro.titulo if loan.ejemplar and loan.ejemplar.libro else None,
        "estado": loan.estado.descripcion if loan.estado else None,
        "fecha_inicio": loan.fecha_inicio,
        "fecha_vencimiento": loan.fecha_vencimiento,
        "socio_id": getattr(loan, "socio_id", None),
        "sede_origen_id": getattr(loan, "sede_origen_id", None),
        "sede_destino_id": getattr(loan, "sede_destino_id", None),
    }


def _is_open_loan(loan):
    return loan.fecha_devolucion is None and (
        loan.estado is None
        or normalize(loan.estado.descripcion) not in {"devuelto", "cancelado", "finalizado"}
    )


@router.get("/prestamos-activos", response_model=List[Dict[str, Any]])
def report_active_loans(db: Session = Depends(get_db)):
    return [
        _loan_report_row(loan)
        for loan in db.query(PrestamoModel).all()
        if _is_open_loan(loan)
        and loan.fecha_vencimiento >= date.today()
        and loan.estado
        and normalize(loan.estado.descripcion) in {"activo", "en curso"}
    ]


@router.get("/prestamos-vencidos", response_model=List[Dict[str, Any]])
def report_overdue_loans(db: Session = Depends(get_db)):
    return [
        _loan_report_row(loan)
        for loan in db.query(PrestamoModel).all()
        if _is_open_loan(loan)
        and loan.fecha_vencimiento < date.today()
        and loan.estado
        and normalize(loan.estado.descripcion) in {"activo", "en curso", "vencido", "atrasado"}
    ]


@router.get("/multas", response_model=List[Dict[str, Any]])
def report_fines(db: Session = Depends(get_db)):
    rows = []
    for fine in db.query(MultaModel).all():
        loans = db.query(PrestamoModel).filter(PrestamoModel.multa_id == fine.id).all()
        rows.append(
            {
                "multa_id": fine.id,
                "monto": fine.monto,
                "fecha": fine.fecha,
                "motivo": fine.motivo,
                "prestamos_ids": [loan.id for loan in loans],
                "socios_ids": [getattr(loan, "socio_id", None) for loan in loans],
            }
        )
    return rows


@router.get("/libros-mas-solicitados", response_model=List[Dict[str, Any]])
def report_most_requested_books(db: Session = Depends(get_db)):
    requested = Counter()
    for loan in db.query(PrestamoModel).all():
        if (
            loan.ejemplar
            and (
                loan.estado is None
                or normalize(loan.estado.descripcion) not in {"cancelado", "cancelada"}
            )
        ):
            requested[loan.ejemplar.libro_id] += 1
    for reservation in db.query(ReservaModel).all():
        state = db.get(EstadoReservaModel, reservation.estado_reserva_id)
        if (
            reservation.ejemplar
            and (state is None or normalize(state.descripcion) != "cancelada")
        ):
            requested[reservation.ejemplar.libro_id] += 1

    books = {book.id: book for book in db.query(LibroModel).all()}
    return [
        {"libro_id": book_id, "titulo": books[book_id].titulo, "solicitudes": count}
        for book_id, count in requested.most_common()
        if book_id in books
    ]


@router.get("/disponibilidad-por-sede", response_model=List[Dict[str, Any]])
def report_availability_by_branch(db: Session = Depends(get_db)):
    counts = defaultdict(lambda: {"ejemplares": 0, "disponibles": 0})
    for item in db.query(EjemplarModel).all():
        key = (item.sede_id, item.libro_id)
        counts[key]["ejemplares"] += 1
        if is_exemplar_available(db, item):
            counts[key]["disponibles"] += 1

    branches = {branch.id: branch for branch in db.query(SedeModel).all()}
    books = {book.id: book for book in db.query(LibroModel).all()}
    items = []
    for (branch_id, book_id), values in counts.items():
        if branch_id in branches and book_id in books:
            items.append(
                {
                    "sede_id": branch_id,
                    "sede": branches[branch_id].nombre,
                    "libro_id": book_id,
                    "titulo": books[book_id].titulo,
                    **values,
                }
            )
    return items


@router.get("/envios", response_model=Dict[str, Any])
def report_shipments(db: Session = Depends(get_db)):
    remitos = db.query(RemitoModel).all()
    received_ids = {
        remito.id
        for remito in remitos
        if (state := db.get(EstadoRemitoModel, remito.estado_remito_id))
        and normalize(state.descripcion) == "recibido"
    }
    durations = [
        (remito.fecha_recepcion - remito.fecha_emision).days
        for remito in remitos
        if remito.id in received_ids and remito.fecha_recepcion is not None
    ]
    incidents = db.query(IncidenciaRemitoModel).count()
    in_transit = sum(
        1
        for remito in remitos
        if (state := db.get(EstadoRemitoModel, remito.estado_remito_id))
        and normalize(state.descripcion) == "en transito"
    )
    total = len(remitos)
    return {
        "remitos_totales": total,
        "recibidos": len(received_ids),
        "incidencias": incidents,
        "en_transito": in_transit,
        "tasa_envios_exitosos": round(len(received_ids) * 100 / total, 2) if total else 0,
        "promedio_transito_dias": round(sum(durations) / len(durations), 2) if durations else None,
    }


@router.get("/material-en-transito", response_model=List[Dict[str, Any]])
def report_material_in_transit(db: Session = Depends(get_db)):
    result = []
    for remito in db.query(RemitoModel).all():
        state = db.get(EstadoRemitoModel, remito.estado_remito_id)
        if state is None or normalize(state.descripcion) != "en transito":
            continue
        loans = db.query(PrestamoInterbibliotecarioModel).filter(
            PrestamoInterbibliotecarioModel.remito_id == remito.id
        ).all()
        loans_by_item = {loan.ejemplar_id: loan for loan in loans}
        details = db.query(DetalleRemitoModel).filter(
            DetalleRemitoModel.remito_id == remito.id
        ).all()
        for detail in details:
            item = db.get(EjemplarModel, detail.ejemplar_id)
            loan = loans_by_item.get(detail.ejemplar_id)
            if item is None or loan is None:
                continue
            result.append(
                {
                    "remito_id": remito.id,
                    "numero": remito.numero,
                    "ejemplar_id": item.id,
                    "codigo": item.codigo,
                    "libro_id": item.libro_id,
                    "titulo": item.libro.titulo,
                    "sede_origen_id": loan.sede_origen_id,
                    "sede_destino_id": loan.sede_destino_id,
                    "fecha_emision": remito.fecha_emision,
                }
            )
    return result


@router.get("/movimientos-interbibliotecarios", response_model=List[Dict[str, Any]])
def report_interlibrary_movements(db: Session = Depends(get_db)):
    grouped = defaultdict(lambda: {"envios": 0, "durations": []})
    for loan in db.query(PrestamoInterbibliotecarioModel).all():
        route = grouped[(loan.sede_origen_id, loan.sede_destino_id)]
        route["envios"] += 1
        remito = db.get(RemitoModel, loan.remito_id) if loan.remito_id else None
        if remito and remito.fecha_recepcion:
            route["durations"].append(
                (remito.fecha_recepcion - remito.fecha_emision).days
            )

    branches = {branch.id: branch.nombre for branch in db.query(SedeModel).all()}
    return [
        {
            "sede_origen_id": origin_id,
            "sede_destino_id": destination_id,
            "sede_origen": branches.get(origin_id),
            "sede_destino": branches.get(destination_id),
            "envios": values["envios"],
            "tiempo_promedio_dias": (
                round(sum(values["durations"]) / len(values["durations"]), 2)
                if values["durations"]
                else None
            ),
        }
        for (origin_id, destination_id), values in grouped.items()
    ]
