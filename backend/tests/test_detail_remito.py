import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models import (
    DetalleRemitoModel,
    EjemplarModel,
    EstadoEjemplarModel,
    EstadoPrestamoModel,
    EstadoRemitoModel,
    LibroModel,
    PrestamoInterbibliotecarioModel,
    RemitoModel,
    SedeModel,
)
from src.routers import detalle_remito


class DetailRemitoTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.prepared = EstadoRemitoModel(descripcion="Preparado")
        self.received = EstadoRemitoModel(descripcion="Recibido")
        self.pending = EstadoPrestamoModel(descripcion="Pendiente")
        self.available = EstadoEjemplarModel(descripcion="Disponible")
        self.origin = SedeModel(
            nombre="Centro",
            direccion="Calle 1",
            email="centro@example.com",
            horarios="Lunes",
            activa=True,
        )
        self.destination = SedeModel(
            nombre="Norte",
            direccion="Calle 2",
            email="norte@example.com",
            horarios="Martes",
            activa=True,
        )
        self.book = LibroModel(
            isbn="9780000000091",
            titulo="Prueba detalle",
            autores=["Autora"],
            editorial="Editorial",
            año_publicacion=2020,
        )
        self.db.add_all(
            [
                self.prepared,
                self.received,
                self.pending,
                self.available,
                self.origin,
                self.destination,
                self.book,
            ]
        )
        self.db.flush()

        self.copy = EjemplarModel(
            codigo="DET-1",
            estado_fisico="Bueno",
            estado_ejemplar_id=self.available.id,
            sede_id=self.origin.id,
            libro_id=self.book.id,
        )
        self.remit = RemitoModel(
            numero="R-DETAIL-1",
            fecha_emision=__import__("datetime").date.today(),
            estado_remito_id=self.prepared.id,
        )
        self.db.add_all([self.copy, self.remit])
        self.db.flush()

        self.loan = PrestamoInterbibliotecarioModel(
            fecha_inicio=__import__("datetime").date.today(),
            fecha_vencimiento=__import__("datetime").date.today(),
            estado_prestamo_id=self.pending.id,
            ejemplar_id=self.copy.id,
            sede_origen_id=self.origin.id,
            sede_destino_id=self.destination.id,
            remito_id=self.remit.id,
        )
        self.db.add(self.loan)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_detail_crud(self):
        created = detalle_remito.create_detalle_remito(
            detalle_remito.DetalleRemitoSchema(
                remito_id=self.remit.id,
                ejemplar_id=self.copy.id,
            ),
            self.db,
        )

        found = detalle_remito.get_detalle_remito(created.id, self.db)
        self.assertEqual(found.id, created.id)

        with self.assertRaises(HTTPException) as error:
            detalle_remito.update_detalle_remito(
                created.id,
                detalle_remito.DetalleRemitoSchema(
                    remito_id=self.remit.id,
                    ejemplar_id=self.copy.id,
                ),
                self.db,
            )
        self.assertEqual(error.exception.status_code, 422)

        detalle_remito.delete_detalle_remito(created.id, self.db)
        self.assertIsNone(self.db.get(DetalleRemitoModel, created.id))

    def test_detail_cannot_be_deleted_after_dispatch(self):
        created = detalle_remito.create_detalle_remito(
            detalle_remito.DetalleRemitoSchema(
                remito_id=self.remit.id,
                ejemplar_id=self.copy.id,
            ),
            self.db,
        )
        self.remit.estado_remito_id = self.received.id
        self.db.commit()

        with self.assertRaises(HTTPException) as error:
            detalle_remito.delete_detalle_remito(created.id, self.db)

        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
