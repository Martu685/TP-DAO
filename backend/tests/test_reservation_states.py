import unittest
from datetime import date
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models import (
    EjemplarModel,
    EstadoEjemplarModel,
    EstadoReservaModel,
    LibroModel,
    SedeModel,
    SocioModel,
)
from src.routers import reserva


class ReservationStateTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.pending = EstadoReservaModel(descripcion="Pendiente")
        self.accepted = EstadoReservaModel(descripcion="Aceptada")
        self.rejected = EstadoReservaModel(descripcion="Rechazada")
        self.cancelled = EstadoReservaModel(descripcion="Cancelada")
        self.attended = EstadoReservaModel(descripcion="Atendida")
        self.available = EstadoEjemplarModel(descripcion="Disponible")
        self.reserved = EstadoEjemplarModel(descripcion="Reservado")
        self.branch = SedeModel(
            nombre="Central",
            direccion="Calle 1",
            email="central@example.com",
            horarios="Lunes a viernes",
            activa=True,
        )
        self.book = LibroModel(
            isbn="9780000000002",
            titulo="Libro de reserva",
            autores=["Autora"],
            editorial="Editorial",
            año_publicacion=2020,
        )
        self.member = SocioModel(
            nombre="Ana",
            apellido="Prueba",
            dni=12345678,
            email="ana@example.com",
            telefono="123456789",
            habilitado=True,
        )
        self.db.add_all(
            [
                self.pending,
                self.accepted,
                self.rejected,
                self.cancelled,
                self.attended,
                self.available,
                self.reserved,
                self.branch,
                self.book,
                self.member,
            ]
        )
        self.db.flush()
        self.copy = EjemplarModel(
            codigo="RES-1",
            estado_fisico="Bueno",
            estado_ejemplar_id=self.available.id,
            sede_id=self.branch.id,
            libro_id=self.book.id,
        )
        self.db.add(self.copy)
        self.db.commit()
        self.member_user = SimpleNamespace(rol="socio", socio_id=self.member.id)
        self.librarian = SimpleNamespace(rol="bibliotecario", socio_id=None)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _schema(self, state_id):
        return reserva.ReservaSchema(
            fecha=date.today(),
            estado_reserva_id=state_id,
            socio_id=self.member.id,
            ejemplar_id=self.copy.id,
            sede_id=self.branch.id,
        )

    def test_reservation_waits_for_acceptance_then_can_be_cancelled(self):
        created = reserva.create_reserva(
            self._schema(self.pending.id),
            self.member_user,
            self.db,
        )
        self.assertEqual(created.estado_reserva_id, self.pending.id)
        self.assertEqual(self.copy.estado_ejemplar_id, self.available.id)

        accepted = reserva.update_reserva(
            created.id,
            self._schema(self.accepted.id),
            self.librarian,
            self.db,
        )
        self.assertEqual(accepted.estado_reserva_id, self.accepted.id)
        self.assertEqual(self.copy.estado_ejemplar_id, self.reserved.id)

        cancelled = reserva.update_reserva(
            created.id,
            self._schema(self.cancelled.id),
            self.member_user,
            self.db,
        )
        self.assertEqual(cancelled.estado_reserva_id, self.cancelled.id)
        self.assertEqual(self.copy.estado_ejemplar_id, self.available.id)

    def test_rejected_reservation_cannot_be_accepted(self):
        created = reserva.create_reserva(
            self._schema(self.pending.id),
            self.member_user,
            self.db,
        )
        reserva.update_reserva(
            created.id,
            self._schema(self.rejected.id),
            self.librarian,
            self.db,
        )

        with self.assertRaises(HTTPException) as error:
            reserva.update_reserva(
                created.id,
                self._schema(self.accepted.id),
                self.librarian,
                self.db,
            )

        self.assertEqual(error.exception.status_code, 422)

    def test_get_and_delete_reservation(self):
        created = reserva.create_reserva(
            self._schema(self.pending.id),
            self.member_user,
            self.db,
        )
        reserva.update_reserva(
            created.id,
            self._schema(self.accepted.id),
            self.librarian,
            self.db,
        )

        found = reserva.get_reserva(created.id, self.member_user, self.db)
        self.assertEqual(found.id, created.id)

        reserva.delete_reserva(created.id, self.member_user, self.db)
        cancelled = self.db.get(EstadoReservaModel, created.estado_reserva_id)
        self.assertEqual(cancelled.descripcion, "Cancelada")
        self.assertEqual(self.copy.estado_ejemplar_id, self.available.id)


if __name__ == "__main__":
    unittest.main()
