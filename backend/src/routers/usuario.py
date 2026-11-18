import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy.orm import Session

from src.auth import (
    create_session,
    hash_password,
    require_roles,
    verify_password,
)
from src.database import get_db
from src.models import SocioModel, UsuarioModel
from src.schemas import APIModel


router = APIRouter(prefix="/api/usuario", tags=["Usuario"])


class RegistroSchema(APIModel):
    nombre: str
    apellido: str
    dni: int
    email: str
    telefono: str
    password: str = Field(min_length=8, max_length=128)


class UsuarioResponse(APIModel):
    id: int
    email: str
    rol: str
    socio_id: int | None


class LoginSchema(APIModel):
    email: str
    password: str


class LoginResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    usuario: UsuarioResponse


class EquipoSchema(APIModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    rol: str = "bibliotecario"


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=422, detail="El email no es válido")
    return normalized


def _create_staff(email: str, password: str, role: str, db: Session):
    normalized_email = _normalize_email(email)
    if role not in {"bibliotecario", "admin"}:
        raise HTTPException(status_code=422, detail="El rol debe ser bibliotecario o admin")
    if db.query(UsuarioModel).filter(UsuarioModel.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")
    user = UsuarioModel(
        email=normalized_email,
        password_hash=hash_password(password),
        rol=role,
        activo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def register_user(registro: RegistroSchema, db: Session = Depends(get_db)):
    email = _normalize_email(registro.email)
    if db.query(UsuarioModel).filter(UsuarioModel.email == email).first():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")
    if db.query(SocioModel).filter(SocioModel.dni == registro.dni).first():
        raise HTTPException(status_code=409, detail="Ya existe un socio con ese DNI")

    socio = SocioModel(
        nombre=registro.nombre,
        apellido=registro.apellido,
        dni=registro.dni,
        email=email,
        telefono=registro.telefono,
        habilitado=True,
    )
    db.add(socio)
    db.flush()
    user = UsuarioModel(
        email=email,
        password_hash=hash_password(registro.password),
        rol="socio",
        socio_id=socio.id,
        activo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/equipo",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin"))],
)
def create_staff_user(
    account: EquipoSchema,
    db: Session = Depends(get_db),
):
    return _create_staff(account.email, account.password, account.rol, db)


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginSchema, db: Session = Depends(get_db)):
    email = _normalize_email(credentials.email)
    user = db.query(UsuarioModel).filter(UsuarioModel.email == email).first()
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    if not user.activo:
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    token, expires_at = create_session(db, user)
    db.commit()
    return LoginResponse(
        access_token=token,
        expires_at=expires_at,
        usuario=user,
    )
