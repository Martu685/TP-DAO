import unittest
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models import (
    EjemplarModel,
    EstadoEjemplarModel,
    EstadoPrestamoModel,
    HistorialLecturaModel,
    LibroModel,
    NotificacionModel,
    PrestamoLocalModel,
    SedeModel,
    SocioModel,
    UsuarioModel,
)
from src.prestamo_workflow import change_prestamo_state
from src.routers import historial, notificacion, prestamo_local


class MemberPortalTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.active = EstadoPrestamoModel(descripcion="Activo")
        self.overdue = EstadoPrestamoModel(descripcion="Vencido")
        self.copy_state = EstadoEjemplarModel(descripcion="Prestado")
        self.branch = SedeModel(
            nombre="Central",
            direccion="Calle 1",
            email="central@example.com",
            horarios="Lunes a viernes",
            activa=True,
        )
        self.book = LibroModel(
            isbn="9780000000001",
            titulo="Libro de prueba",
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
        self.other_member = SocioModel(
            nombre="Luis",
            apellido="Prueba",
            dni=87654321,
            email="luis@example.com",
            telefono="987654321",
            habilitado=True,
        )
        self.db.add_all(
            [
                self.active,
                self.overdue,
                self.copy_state,
                self.branch,
                self.book,
                self.member,
                self.other_member,
            ]
        )
        self.db.flush()

        self.member_user = UsuarioModel(
            email=self.member.email,
            password_hash="unused",
            rol="socio",
            socio_id=self.member.id,
            activo=True,
        )
        self.librarian = UsuarioModel(
            email="librarian@example.com",
            password_hash="unused",
            rol="bibliotecario",
            socio_id=None,
            activo=True,
        )
        self.copy = EjemplarModel(
            codigo="TEST-1",
            estado_fisico="Bueno",
            estado_ejemplar_id=self.copy_state.id,
            sede_id=self.branch.id,
            libro_id=self.book.id,
        )
        self.other_copy = EjemplarModel(
            codigo="TEST-2",
            estado_fisico="Bueno",
            estado_ejemplar_id=self.copy_state.id,
            sede_id=self.branch.id,
            libro_id=self.book.id,
        )
        self.db.add_all([self.member_user, self.librarian, self.copy, self.other_copy])
        self.db.flush()

        today = date.today()
        self.member_loan = PrestamoLocalModel(
            fecha_inicio=today - timedelta(days=3),
            fecha_vencimiento=today + timedelta(days=4),
            fecha_devolucion=None,
            estado_prestamo_id=self.active.id,
            ejemplar_id=self.copy.id,
            multa_id=None,
            devolucion_id=None,
            sede_origen_id=self.branch.id,
            socio_id=self.member.id,
        )
        self.other_loan = PrestamoLocalModel(
            fecha_inicio=today - timedelta(days=5),
            fecha_vencimiento=today + timedelta(days=2),
            fecha_devolucion=None,
            estado_prestamo_id=self.active.id,
            ejemplar_id=self.other_copy.id,
            multa_id=None,
            devolucion_id=None,
            sede_origen_id=self.branch.id,
            socio_id=self.other_member.id,
        )
        self.db.add_all(
            [
                self.member_loan,
                self.other_loan,
                HistorialLecturaModel(
                    fecha=today,
                    socio_id=self.member.id,
                    libro_id=self.book.id,
                    prestamo_id=None,
                ),
                HistorialLecturaModel(
                    fecha=today - timedelta(days=1),
                    socio_id=self.other_member.id,
                    libro_id=self.book.id,
                    prestamo_id=None,
                ),
                NotificacionModel(
                    fecha=datetime.now(),
                    canal="sistema",
                    mensaje="Notificación propia",
                    socio_id=self.member.id,
                ),
                NotificacionModel(
                    fecha=datetime.now(),
                    canal="sistema",
                    mensaje="Notificación ajena",
                    socio_id=self.other_member.id,
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_member_reads_only_own_history_loans_and_notifications(self):
        history_rows = historial.get_historial_lecturas(
            socio_id=None,
            libro_id=None,
            db=self.db,
            current_user=self.member_user,
        )
        loan_rows = prestamo_local.get_prestamos_locales(
            db=self.db,
            current_user=self.member_user,
        )
        notification_rows = notificacion.get_notificaciones(
            socio_id=None,
            db=self.db,
            current_user=self.member_user,
        )

        self.assertEqual([row.socio_id for row in history_rows], [self.member.id])
        self.assertEqual([row.socio_id for row in loan_rows], [self.member.id])
        self.assertEqual(
            [row.mensaje for row in notification_rows],
            ["Notificación propia"],
        )

    def test_member_cannot_request_another_members_history_or_notifications(self):
        with self.assertRaises(HTTPException) as history_error:
            historial.get_historial_lecturas(
                socio_id=self.other_member.id,
                libro_id=None,
                db=self.db,
                current_user=self.member_user,
            )
        self.assertEqual(history_error.exception.status_code, 403)

        with self.assertRaises(HTTPException) as notification_error:
            notificacion.get_notificaciones(
                socio_id=self.other_member.id,
                db=self.db,
                current_user=self.member_user,
            )
        self.assertEqual(notification_error.exception.status_code, 403)

    def test_librarian_can_view_all_members_records(self):
        self.assertEqual(
            len(
                historial.get_historial_lecturas(
                    db=self.db,
                    current_user=self.librarian,
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                prestamo_local.get_prestamos_locales(
                    db=self.db,
                    current_user=self.librarian,
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                notificacion.get_notificaciones(
                    db=self.db,
                    current_user=self.librarian,
                )
            ),
            2,
        )

    def test_status_change_automatically_creates_member_notification(self):
        change_prestamo_state(
            self.db,
            self.member_loan,
            self.overdue.id,
        )
        self.db.commit()

        rows = notificacion.get_notificaciones(
            socio_id=None,
            db=self.db,
            current_user=self.member_user,
        )
        self.assertEqual(len(rows), 2)
        self.assertIn("cambió de Activo a Vencido", rows[0].mensaje)


if __name__ == "__main__":
    unittest.main()
