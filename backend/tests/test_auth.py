import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src import auth
from src.database import Base
from src.routers import usuario


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_registration_login_and_bearer_authentication(self):
        user = usuario.register_user(
            usuario.RegistroSchema(
                nombre="Ana",
                apellido="Prueba",
                dni=12345678,
                email="ANA@example.com",
                telefono="123456789",
                password="contraseña-segura",
            ),
            self.db,
        )

        self.assertEqual(user.email, "ana@example.com")
        self.assertEqual(user.rol, "socio")
        self.assertIsNotNone(user.socio_id)

        login = usuario.login(
            usuario.LoginSchema(
                email="ana@example.com",
                password="contraseña-segura",
            ),
            self.db,
        )
        authenticated = auth.get_current_user(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=login.access_token,
            ),
            self.db,
        )

        self.assertEqual(authenticated.id, user.id)
        self.assertEqual(login.token_type, "bearer")

    def test_login_rejects_incorrect_password(self):
        user = usuario.register_user(
            usuario.RegistroSchema(
                nombre="Ana",
                apellido="Prueba",
                dni=12345678,
                email="ana@example.com",
                telefono="123456789",
                password="contraseña-segura",
            ),
            self.db,
        )
        self.db.commit()

        with self.assertRaises(HTTPException) as error:
            usuario.login(
                usuario.LoginSchema(
                    email=user.email,
                    password="incorrecta",
                ),
                self.db,
            )

        self.assertEqual(error.exception.status_code, 401)

    def test_role_dependency_rejects_a_socio(self):
        user = usuario.register_user(
            usuario.RegistroSchema(
                nombre="Ana",
                apellido="Prueba",
                dni=12345678,
                email="ana@example.com",
                telefono="123456789",
                password="contraseña-segura",
            ),
            self.db,
        )
        admin_only = auth.require_roles("admin")

        with self.assertRaises(HTTPException) as error:
            admin_only(user)

        self.assertEqual(error.exception.status_code, 403)
