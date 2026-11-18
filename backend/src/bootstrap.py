import os
import unicodedata

from src.auth import hash_password
from src.database import SessionLocal
from src.models import (
    EstadoEjemplarModel,
    EstadoPrestamoModel,
    EstadoRemitoModel,
    EstadoReservaModel,
    UsuarioModel,
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
        (EstadoPrestamoModel, ("Pendiente", "Activo", "Vencido", "Devuelto")),
        (EstadoEjemplarModel, ("Disponible", "Prestado", "Reservado")),
        (
            EstadoReservaModel,
            ("Pendiente", "Aceptada", "Rechazada", "Cancelada", "Atendida"),
        ),
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


def initialize_admin_account():
    email = os.getenv("BIBLIOTECA_ADMIN_EMAIL")
    password = os.getenv("BIBLIOTECA_ADMIN_PASSWORD")
    if not email and not password:
        return
    if not email or not password:
        raise RuntimeError(
            "BIBLIOTECA_ADMIN_EMAIL y BIBLIOTECA_ADMIN_PASSWORD deben configurarse juntos"
        )
    if len(password) < 8:
        raise RuntimeError("BIBLIOTECA_ADMIN_PASSWORD debe tener al menos 8 caracteres")
    email = email.strip().lower()
    db = SessionLocal()
    try:
        existing = db.query(UsuarioModel).filter(UsuarioModel.email == email).first()
        if existing is None:
            db.add(
                UsuarioModel(
                    email=email,
                    password_hash=hash_password(password),
                    rol="admin",
                    activo=True,
                )
            )
            db.commit()
        elif existing.rol != "admin":
            raise RuntimeError(
                "BIBLIOTECA_ADMIN_EMAIL ya está asociado a una cuenta que no es admin"
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
