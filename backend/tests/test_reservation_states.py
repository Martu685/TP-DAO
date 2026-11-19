import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models import (
    EjemplarModel,
    EstadoEjemplarModel,
    EstadoPrestamoModel,
    EstadoReservaModel,
    LibroModel,
    NotificacionModel,
    ReservaModel,
    SedeModel,
    SocioModel,
)
from src.routers import estado, prestamo_local, reserva


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
        self.active_loan = EstadoPrestamoModel(descripcion="Activo")
        self.available = EstadoEjemplarModel(descripcion="Disponible")
        self.borrowed = EstadoEjemplarModel(descripcion="Prestado")
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
                self.active_loan,
                self.available,
                self.borrowed,
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
        messages = [
            notification.mensaje
            for notification in self.db.query(NotificacionModel)
            .order_by(NotificacionModel.id)
            .all()
        ]
        self.assertEqual(
            messages,
            [
                f"La reserva #{created.id} cambió de Pendiente a Aceptada.",
                f"La reserva #{created.id} cambió de Aceptada a Cancelada.",
            ],
        )

    def test_reservation_state_catalog_includes_attended(self):
        states = estado.get_estados_reserva(self.db)

        self.assertIn(self.attended, states)

    def test_socios_only_list_their_own_reservations(self):
        own_reservation = reserva.create_reserva(
            self._schema(self.pending.id),
            self.member_user,
            self.db,
        )
        other_member = SocioModel(
            nombre="Luis",
            apellido="Prueba",
            dni=87654321,
            email="luis@example.com",
            telefono="987654321",
            habilitado=True,
        )
        self.db.add(other_member)
        self.db.flush()
        other_reservation = ReservaModel(
            fecha=date.today(),
            estado_reserva_id=self.pending.id,
            socio_id=other_member.id,
            ejemplar_id=self.copy.id,
            sede_id=self.branch.id,
        )
        self.db.add(other_reservation)
        self.db.commit()

        member_rows = reserva.get_reservas(self.member_user, self.db)
        librarian_rows = reserva.get_reservas(self.librarian, self.db)

        self.assertEqual([row.id for row in member_rows], [own_reservation.id])
        self.assertEqual(
            {row.id for row in librarian_rows},
            {own_reservation.id, other_reservation.id},
        )

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
        messages = [
            notification.mensaje
            for notification in self.db.query(NotificacionModel)
            .order_by(NotificacionModel.id)
            .all()
        ]
        self.assertEqual(
            messages[-1],
            f"La reserva #{created.id} cambió de Aceptada a Cancelada.",
        )

    def test_ready_reservation_notification_when_loan_marks_it_attended(self):
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

        loan = prestamo_local.create_prestamo_local(
            prestamo_local.PrestamoLocalSchema(
                fecha_inicio=date.today(),
                fecha_vencimiento=date.today() + timedelta(days=14),
                fecha_devolucion=None,
                estado_prestamo_id=self.active_loan.id,
                ejemplar_id=self.copy.id,
                multa_id=None,
                devolucion_id=None,
                sede_origen_id=self.branch.id,
                socio_id=self.member.id,
            ),
            self.db,
        )

        reservation_state = self.db.get(EstadoReservaModel, created.estado_reserva_id)
        self.assertEqual(reservation_state.descripcion, "Atendida")
        self.assertEqual(loan.socio_id, self.member.id)
        messages = [
            notification.mensaje
            for notification in self.db.query(NotificacionModel)
            .order_by(NotificacionModel.id)
            .all()
        ]
        self.assertEqual(
            messages[-1],
            f"La reserva #{created.id} cambió de Aceptada a Atendida.",
        )


if __name__ == "__main__":
    unittest.main()
