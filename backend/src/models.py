from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.database import Base

# ==================== TABLAS MAESTRAS DE ESTADOS ====================

class EstadoReservaModel(Base):
    __tablename__ = "estados_reserva"
    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String, nullable=False)

class EstadoEjemplarModel(Base):
    __tablename__ = "estados_ejemplar"
    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String, nullable=False)

class EstadoRemitoModel(Base):
    __tablename__ = "estados_remito"
    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String, nullable=False)

class EstadoPrestamoModel(Base):
    __tablename__ = "estados_prestamo"
    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String, nullable=False)


class UsuarioModel(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    rol = Column(String, nullable=False, default="socio")
    socio_id = Column(Integer, ForeignKey("socios.id"), unique=True, nullable=True)
    sede_id = Column(Integer, ForeignKey("sedes.id"), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    socio = relationship("SocioModel")
    sede = relationship("SedeModel")


class SesionModel(Base):
    __tablename__ = "sesiones"
    token_hash = Column(String, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    vence_en = Column(DateTime, nullable=False)

    usuario = relationship("UsuarioModel")

# ==================== ENTIDADES PRINCIPALES ====================

class SocioModel(Base):
    __tablename__ = "socios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    dni = Column(Integer, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    telefono = Column(String, nullable=False)
    habilitado = Column(Boolean, default=True)

    notificaciones = relationship("NotificacionModel", back_populates="socio")
    reservas = relationship("ReservaModel", back_populates="socio")

class NotificacionModel(Base):
    __tablename__ = "notificaciones"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, nullable=False)
    canal = Column(String, nullable=False)
    mensaje = Column(String, nullable=False)
    socio_id = Column(Integer, ForeignKey("socios.id"), nullable=False)

    socio = relationship("SocioModel", back_populates="notificaciones")

class SedeModel(Base):
    __tablename__ = "sedes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    direccion = Column(String, nullable=False)
    email = Column(String, nullable=False)
    horarios = Column(String, nullable=False)
    activa = Column(Boolean, default=True)

    ejemplares = relationship("EjemplarModel", back_populates="sede")

class LibroModel(Base):
    __tablename__ = "libros"
    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String, unique=True, index=True, nullable=False)
    titulo = Column(String, nullable=False)
    autores = Column(JSON, nullable=False)
    editorial = Column(String, nullable=False)
    año_publicacion = Column("ao_publicacion", Integer, nullable=False)

    ejemplares = relationship("EjemplarModel", back_populates="libro")

class EjemplarModel(Base):
    __tablename__ = "ejemplares"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    estado_fisico = Column(String, nullable=False)
    estado_ejemplar_id = Column(Integer, ForeignKey("estados_ejemplar.id"), nullable=False)
    sede_id = Column(Integer, ForeignKey("sedes.id"), nullable=False)
    libro_id = Column(Integer, ForeignKey("libros.id"), nullable=False)

    libro = relationship("LibroModel", back_populates="ejemplares")
    sede = relationship("SedeModel", back_populates="ejemplares")
    estado_ejemplar = relationship("EstadoEjemplarModel")

class ReservaModel(Base):
    __tablename__ = "reservas"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False)
    estado_reserva_id = Column(Integer, ForeignKey("estados_reserva.id"), nullable=False)
    socio_id = Column(Integer, ForeignKey("socios.id"), nullable=False)
    ejemplar_id = Column(Integer, ForeignKey("ejemplares.id"), nullable=False)
    sede_id = Column(Integer, ForeignKey("sedes.id"), nullable=False)

    socio = relationship("SocioModel", back_populates="reservas")
    ejemplar = relationship("EjemplarModel")
    sede = relationship("SedeModel")

class RemitoModel(Base):
    __tablename__ = "remitos"
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True, nullable=False)
    fecha_emision = Column(Date, nullable=False)
    fecha_recepcion = Column(Date, nullable=True)
    estado_remito_id = Column(Integer, ForeignKey("estados_remito.id"), nullable=False)

    detalles = relationship("DetalleRemitoModel", back_populates="remito", cascade="all, delete-orphan")
    incidencias = relationship(
        "IncidenciaRemitoModel", back_populates="remito", cascade="all, delete-orphan"
    )


class IncidenciaRemitoModel(Base):
    __tablename__ = "incidencias_remito"
    id = Column(Integer, primary_key=True, index=True)
    remito_id = Column(Integer, ForeignKey("remitos.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    descripcion = Column(String, nullable=False)
    resuelta = Column(Boolean, nullable=False, default=False)

    remito = relationship("RemitoModel", back_populates="incidencias")

class DetalleRemitoModel(Base):
    __tablename__ = "detalles_remito"
    id = Column(Integer, primary_key=True, index=True)
    remito_id = Column(Integer, ForeignKey("remitos.id"), nullable=False)
    ejemplar_id = Column(Integer, ForeignKey("ejemplares.id"), nullable=False)

    remito = relationship("RemitoModel", back_populates="detalles")

class MultaModel(Base):
    __tablename__ = "multas"
    id = Column(Integer, primary_key=True, index=True)
    monto = Column(Float, nullable=False)
    fecha = Column(Date, nullable=False)
    motivo = Column(String, nullable=False)

class DevolucionModel(Base):
    __tablename__ = "devoluciones"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False)
    observaciones = Column(String, nullable=True)


class HistorialLecturaModel(Base):
    __tablename__ = "historial_lecturas"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False)
    socio_id = Column(Integer, ForeignKey("socios.id"), nullable=False)
    libro_id = Column(Integer, ForeignKey("libros.id"), nullable=False)
    prestamo_id = Column(Integer, ForeignKey("prestamos.id"), unique=True, nullable=True)

# ==================== HERENCIA DE PR�STAMOS ====================

class PrestamoModel(Base):
    __tablename__ = "prestamos"
    id = Column(Integer, primary_key=True, index=True)
    fecha_inicio = Column(Date, nullable=False)
    fecha_vencimiento = Column(Date, nullable=False)
    fecha_devolucion = Column(Date, nullable=True)
    tipo_prestamo = Column(String, nullable=False)

    estado_prestamo_id = Column(Integer, ForeignKey("estados_prestamo.id"), nullable=False)
    ejemplar_id = Column(Integer, ForeignKey("ejemplares.id"), nullable=False)
    multa_id = Column(Integer, ForeignKey("multas.id"), nullable=True)
    devolucion_id = Column(Integer, ForeignKey("devoluciones.id"), nullable=True)

    estado = relationship("EstadoPrestamoModel")
    ejemplar = relationship("EjemplarModel")
    multa = relationship("MultaModel")
    devolucion = relationship("DevolucionModel")

    __mapper_args__ = {
        "polymorphic_identity": "prestamo_base",
        "polymorphic_on": tipo_prestamo,
    }

class PrestamoLocalModel(PrestamoModel):
    __tablename__ = "prestamos_locales"
    id = Column(Integer, ForeignKey("prestamos.id"), primary_key=True)
    sede_origen_id = Column(Integer, ForeignKey("sedes.id"), nullable=False)
    socio_id = Column(Integer, ForeignKey("socios.id"), nullable=False)

    sede_origen = relationship("SedeModel")
    socio = relationship("SocioModel")

    __mapper_args__ = {
        "polymorphic_identity": "prestamo_local",
    }

class PrestamoInterbibliotecarioModel(PrestamoModel):
    __tablename__ = "prestamos_interbibliotecarios"
    id = Column(Integer, ForeignKey("prestamos.id"), primary_key=True)
    sede_origen_id = Column(Integer, ForeignKey("sedes.id"), nullable=False)
    sede_destino_id = Column(Integer, ForeignKey("sedes.id"), nullable=False)
    remito_id = Column(Integer, ForeignKey("remitos.id"), nullable=True)

    sede_origen = relationship("SedeModel", foreign_keys=[sede_origen_id])
    sede_destino = relationship("SedeModel", foreign_keys=[sede_destino_id])
    remito = relationship("RemitoModel")

    __mapper_args__ = {
        "polymorphic_identity": "prestamo_interbibliotecario",
    }
