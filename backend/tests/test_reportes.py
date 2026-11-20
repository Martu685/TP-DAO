import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models import (
    EjemplarModel,
    EstadoEjemplarModel,
    EstadoReservaModel,
    LibroModel,
    ReservaModel,
    SedeModel,
    SocioModel,
)
from src.routers.reportes import report_most_requested_books


class MostRequestedBooksReportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.branch = SedeModel(
            nombre="Central",
            direccion="Calle 1",
            email="central@example.com",
            horarios="Lunes a viernes",
            activa=True,
        )
        self.member = SocioModel(
            nombre="Ana",
            apellido="Prueba",
            dni=12345678,
            email="ana@example.com",
            telefono="123456789",
            habilitado=True,
        )
        self.book = LibroModel(
            isbn="9780000000001",
            titulo="Libro solicitado",
            autores=["Autora"],
            editorial="Editorial",
            año_publicacion=2020,
        )
        self.available = EstadoEjemplarModel(descripcion="Disponible")
        self.accepted = EstadoReservaModel(descripcion="Aceptada")
        self.cancelled = EstadoReservaModel(descripcion="Cancelada")
        self.db.add_all(
            [
                self.branch,
                self.member,
                self.book,
                self.available,
                self.accepted,
                self.cancelled,
            ]
        )
        self.db.flush()

        self.copy = EjemplarModel(
            codigo="REP-1",
            estado_fisico="Bueno",
            estado_ejemplar_id=self.available.id,
            sede_id=self.branch.id,
            libro_id=self.book.id,
        )
        self.db.add(self.copy)
        self.db.flush()
        self.db.add_all(
            [
                ReservaModel(
                    fecha=date.today(),
                    estado_reserva_id=self.accepted.id,
                    socio_id=self.member.id,
                    ejemplar_id=self.copy.id,
                    sede_id=self.branch.id,
                ),
                ReservaModel(
                    fecha=date.today(),
                    estado_reserva_id=self.cancelled.id,
                    socio_id=self.member.id,
                    ejemplar_id=self.copy.id,
                    sede_id=self.branch.id,
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_counts_non_cancelled_reservations_using_state_foreign_key(self):
        self.assertEqual(
            report_most_requested_books(self.db),
            [
                {
                    "libro_id": self.book.id,
                    "titulo": self.book.titulo,
                    "solicitudes": 1,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
