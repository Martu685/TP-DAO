from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.auth import get_current_user, require_roles
from src.database import get_db
from src.models import EjemplarModel, LibroModel
from src.schemas import APIModel

router = APIRouter(
    prefix="/api/libro",
    tags=["Libro"],
    dependencies=[Depends(get_current_user)],
)

class LibroSchema(APIModel):
    isbn: str
    titulo: str
    autores: List[str]
    editorial: str
    año_publicacion: int

class LibroResponse(LibroSchema):
    id: int

@router.post(
    "",
    response_model=LibroResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def create_libro(libro: LibroSchema, db: Session = Depends(get_db)):
    db_libro = LibroModel(**libro.model_dump())
    db.add(db_libro)
    db.commit()
    db.refresh(db_libro)
    return db_libro

@router.get("", response_model=List[LibroResponse])
def get_libros(db: Session = Depends(get_db)):
    return db.query(LibroModel).all()

@router.put(
    "/{libro_id}",
    response_model=LibroResponse,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def update_libro(libro_id: int, libro_data: LibroSchema, db: Session = Depends(get_db)):
    db_libro = db.query(LibroModel).filter(LibroModel.id == libro_id).first()
    if not db_libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    for key, value in libro_data.model_dump().items():
        setattr(db_libro, key, value)
    db.commit()
    db.refresh(db_libro)
    return db_libro

@router.delete(
    "/{libro_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("bibliotecario", "admin"))],
)
def delete_libro(libro_id: int, db: Session = Depends(get_db)):
    db_libro = db.query(LibroModel).filter(LibroModel.id == libro_id).first()
    if not db_libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    if db.query(EjemplarModel).filter(EjemplarModel.libro_id == libro_id).first():
        raise HTTPException(
            status_code=409,
            detail="No se puede borrar un libro con ejemplares registrados",
        )
    db.delete(db_libro)
    db.commit()
    return None
