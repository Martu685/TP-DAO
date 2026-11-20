import unittest

import flet as ft

from frontend.ui.components import notify, update_form_errors
from frontend.ui.views.reservas.reservas import _new_reservation


class FakePage:
    def __init__(self):
        self.dialog = None
        self.snack_bar = None
        self.updated = False
        self.popped = False

    def show_dialog(self, dialog):
        self.dialog = dialog

    def update(self):
        self.updated = True

    def pop_dialog(self):
        self.popped = True


class FormErrorTests(unittest.TestCase):
    def test_field_errors_are_inline_and_clear_on_next_validation(self):
        page = FakePage()
        text_field = ft.TextField()
        dropdown = ft.Dropdown()

        invalid = update_form_errors(
            page,
            [text_field, dropdown],
            [
                (text_field, "Campo obligatorio."),
                (dropdown, "Seleccioná una opción."),
            ],
        )

        self.assertTrue(invalid)
        self.assertEqual(text_field.error, "Campo obligatorio.")
        self.assertEqual(dropdown.error_text, "Seleccioná una opción.")

        valid = update_form_errors(page, [text_field, dropdown], [])

        self.assertFalse(valid)
        self.assertIsNone(text_field.error)
        self.assertIsNone(dropdown.error_text)

    def test_error_notification_opens_reusable_dialog(self):
        page = FakePage()

        notify(page, "No se pudo guardar.", error=True)

        self.assertIsInstance(page.dialog, ft.AlertDialog)
        self.assertEqual(page.dialog.content.value, "No se pudo guardar.")
        page.dialog.actions[0].on_click(None)
        self.assertTrue(page.popped)

    def test_reservation_validation_stays_inside_form(self):
        class FakeApi:
            def request(self, path):
                responses = {
                    "/api/socio": [
                        {
                            "id": 1,
                            "nombre": "Ada",
                            "apellido": "Lovelace",
                            "dni": 12345678,
                            "habilitado": True,
                        }
                    ],
                    "/api/sede": [{"id": 1, "nombre": "Central", "activa": True}],
                    "/api/ejemplar": [
                        {"id": 1, "codigo": "CEN-0001", "libro_id": 1}
                    ],
                    "/api/libro": [{"id": 1, "titulo": "Libro demo"}],
                    "/api/estado/reserva": [
                        {"id": 1, "descripcion": "Pendiente"}
                    ],
                }
                return responses[path]

        class FakeApp:
            def __init__(self):
                self.page = FakePage()
                self.api = FakeApi()

        app = FakeApp()
        _new_reservation(app)
        dialog = app.page.dialog

        dialog.actions[1].on_click(None)

        fields = dialog.content.content.controls
        self.assertEqual(
            [field.error_text for field in fields[1:]],
            ["Seleccioná una opción."] * 3,
        )
        self.assertIs(app.page.dialog, dialog)


if __name__ == "__main__":
    unittest.main()
