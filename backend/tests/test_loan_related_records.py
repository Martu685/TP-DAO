import unittest
from datetime import date, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from src.database import Base
from src.models import (
    DevolucionModel,
    EjemplarModel,
    EstadoEjemplarModel,
    EstadoPrestamoModel,
    LibroModel,
    MultaModel,
    PrestamoLocalModel,
    SocioModel,
    SedeModel,
)
from src.routers import devolucion, multa


class LoanRelatedRecordTests(unittest.TestCase):
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
        self.session = sessionmaker(bind=self.engine)()

        self.active = EstadoPrestamoModel(descripcion="Activo")
        self.overdue = EstadoPrestamoModel(descripcion="Vencido")
        self.returned = EstadoPrestamoModel(descripcion="Devuelto")
        self.copy_borrowed = EstadoEjemplarModel(descripcion="Prestado")
        self.copy_available = EstadoEjemplarModel(descripcion="Disponible")
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
        self.session.add_all(
            [
                self.active,
                self.overdue,
                self.returned,
                self.copy_borrowed,
                self.copy_available,
                self.branch,
                self.book,
                self.member,
            ]
        )
        self.session.flush()
        self.copy = EjemplarModel(
            codigo="TEST-1",
            estado_fisico="Bueno",
            estado_ejemplar_id=self.copy_borrowed.id,
            sede_id=self.branch.id,
            libro_id=self.book.id,
        )
        self.session.add(self.copy)
        self.session.flush()
        self.loan = PrestamoLocalModel(
            fecha_inicio=date.today() - timedelta(days=10),
            fecha_vencimiento=date.today() - timedelta(days=2),
            fecha_devolucion=None,
            estado_prestamo_id=self.active.id,
            ejemplar_id=self.copy.id,
            multa_id=None,
            devolucion_id=None,
            sede_origen_id=self.branch.id,
            socio_id=self.member.id,
        )
        self.session.add(self.loan)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_editing_return_updates_loan_and_recalculates_automatic_fine(self):
        with patch.object(devolucion, "MULTA_DIARIA", 100):
            return_record = devolucion.return_loan(
                self.loan.id,
                devolucion.LoanReturnRequest(
                    fecha=date.today(),
                    observaciones="Inicial",
                    estado_fisico="Bueno",
                ),
                self.session,
            )
            automatic_fine_id = self.loan.multa_id

            updated = devolucion.update_devolucion(
                return_record.id,
                devolucion.DevolucionSchema(
                    fecha=self.loan.fecha_vencimiento + timedelta(days=1),
                    observaciones="Actualizada",
                ),
                self.session,
            )

        self.assertEqual(updated.observaciones, "Actualizada")
        self.assertEqual(self.loan.fecha_devolucion, updated.fecha)
        self.assertEqual(self.loan.multa_id, automatic_fine_id)
        self.assertEqual(self.session.get(MultaModel, automatic_fine_id).monto, 100)

        devolucion.update_devolucion(
            return_record.id,
            devolucion.DevolucionSchema(
                fecha=self.loan.fecha_vencimiento,
                observaciones=None,
            ),
            self.session,
        )
        self.assertIsNone(self.loan.multa_id)
        self.assertIsNone(self.session.get(MultaModel, automatic_fine_id))

    def test_deleting_return_reopens_loan_and_removes_automatic_fine(self):
        with patch.object(devolucion, "MULTA_DIARIA", 100):
            return_record = devolucion.return_loan(
                self.loan.id,
                devolucion.LoanReturnRequest(
                    fecha=date.today(),
                    observaciones=None,
                    estado_fisico="Bueno",
                ),
                self.session,
            )
            automatic_fine_id = self.loan.multa_id
            devolucion.delete_devolucion(return_record.id, self.session)

        self.assertIsNone(self.loan.fecha_devolucion)
        self.assertIsNone(self.loan.devolucion_id)
        self.assertEqual(self.loan.estado_prestamo_id, self.overdue.id)
        self.assertEqual(self.copy.estado_ejemplar_id, self.copy_borrowed.id)
        self.assertIsNone(self.loan.multa_id)
        self.assertIsNone(self.session.get(DevolucionModel, return_record.id))
        self.assertIsNone(self.session.get(MultaModel, automatic_fine_id))

    def test_deleting_return_preserves_a_manual_fine(self):
        manual_fine = multa.create_multa(
            multa.MultaCreateRequest(
                monto=250,
                fecha=date.today(),
                motivo="Daño del ejemplar",
                prestamo_id=self.loan.id,
            ),
            self.session,
        )
        with patch.object(devolucion, "MULTA_DIARIA", 100):
            return_record = devolucion.return_loan(
                self.loan.id,
                devolucion.LoanReturnRequest(
                    fecha=date.today(),
                    observaciones=None,
                    estado_fisico="Bueno",
                ),
                self.session,
            )
            devolucion.delete_devolucion(return_record.id, self.session)

        self.assertEqual(self.loan.multa_id, manual_fine.id)
        self.assertIsNotNone(self.session.get(MultaModel, manual_fine.id))

    def test_deleting_return_reopens_on_time_loan_as_active(self):
        self.loan.fecha_vencimiento = date.today() + timedelta(days=2)
        self.session.commit()
        return_record = devolucion.return_loan(
            self.loan.id,
            devolucion.LoanReturnRequest(
                fecha=date.today(),
                observaciones=None,
                estado_fisico="Bueno",
            ),
            self.session,
        )

        devolucion.delete_devolucion(return_record.id, self.session)

        self.assertEqual(self.loan.estado_prestamo_id, self.active.id)
        self.assertEqual(self.copy.estado_ejemplar_id, self.copy_borrowed.id)

    def test_creating_and_deleting_manual_fine_updates_loan_link(self):
        record = multa.create_multa(
            multa.MultaCreateRequest(
                monto=250,
                fecha=date.today(),
                motivo="Daño del ejemplar",
                prestamo_id=self.loan.id,
            ),
            self.session,
        )
        self.assertEqual(self.loan.multa_id, record.id)

        updated = multa.update_multa(
            record.id,
            multa.MultaSchema(
                monto=300,
                fecha=date.today(),
                motivo="Reparación del ejemplar",
            ),
            self.session,
        )
        self.assertEqual(updated.monto, 300)
        self.assertEqual(self.loan.multa_id, record.id)

        multa.delete_multa(record.id, self.session)
        self.assertIsNone(self.loan.multa_id)
        self.assertIsNone(self.session.get(MultaModel, record.id))

    def test_rejects_a_second_fine_for_the_same_loan(self):
        multa.create_multa(
            multa.MultaCreateRequest(
                monto=100,
                fecha=date.today(),
                motivo="Primera multa",
                prestamo_id=self.loan.id,
            ),
            self.session,
        )

        with self.assertRaises(HTTPException) as error:
            multa.create_multa(
                multa.MultaCreateRequest(
                    monto=200,
                    fecha=date.today(),
                    motivo="Segunda multa",
                    prestamo_id=self.loan.id,
                ),
                self.session,
            )

        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
