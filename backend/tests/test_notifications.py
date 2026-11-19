import unittest
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models import SocioModel
from src.routers import notificacion


class NotificationEndpointTests(unittest.TestCase):
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
        self.member = SocioModel(
            nombre="Ana",
            apellido="Prueba",
            dni=12345678,
            email="ana@example.com",
            telefono="123456789",
            habilitado=True,
        )
        self.session.add(self.member)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_create_and_get_notification(self):
        created = notificacion.create_notificacion(
            notificacion.NotificacionSchema(
                fecha=datetime(2026, 11, 19, 12, 0),
                canal="email",
                mensaje="Tenés una reserva disponible",
                socio_id=self.member.id,
            ),
            self.session,
        )

        notifications = notificacion.get_notificaciones(
            socio_id=self.member.id,
            db=self.session,
        )

        self.assertEqual(created.id, notifications[0].id)
        self.assertEqual(notifications[0].mensaje, "Tenés una reserva disponible")

    def test_create_notification_rejects_unknown_member(self):
        with self.assertRaises(HTTPException) as error:
            notificacion.create_notificacion(
                notificacion.NotificacionSchema(
                    fecha=datetime.now(),
                    canal="sistema",
                    mensaje="Prueba",
                    socio_id=999,
                ),
                self.session,
            )

        self.assertEqual(error.exception.status_code, 404)

    def test_create_notification_rejects_empty_values(self):
        with self.assertRaises(HTTPException) as error:
            notificacion.create_notificacion(
                notificacion.NotificacionSchema(
                    fecha=datetime.now(),
                    canal=" ",
                    mensaje=" ",
                    socio_id=self.member.id,
                ),
                self.session,
            )

        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
