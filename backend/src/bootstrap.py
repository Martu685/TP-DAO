import unicodedata

from src.database import SessionLocal
from src.models import (
    EstadoEjemplarModel,
    EstadoPrestamoModel,
    EstadoRemitoModel,
    EstadoReservaModel,
)


def _normalize(value):
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def initialize_reference_data():
    catalogs = (
        (EstadoPrestamoModel, ("Pendiente", "Activo", "Vencido", "Devuelto", "Cancelado")),
        (
            EstadoEjemplarModel,
            (
                "Disponible",
                "Prestado",
                "Reservado",
                "En tránsito",
                "No disponible",
                "Dañado",
                "Extraviado",
                "Destruido",
            ),
        ),
        (EstadoReservaModel, ("Pendiente", "Disponible", "Atendida", "Cancelada")),
        (
            EstadoRemitoModel,
            ("Preparado", "En tránsito", "Recibido", "Incidencia", "Cancelado"),
        ),
    )
    db = SessionLocal()
    try:
        for model, descriptions in catalogs:
            existing = {
                _normalize(description)
                for (description,) in db.query(model.descripcion).all()
            }
            for description in descriptions:
                if _normalize(description) not in existing:
                    db.add(model(descripcion=description))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()