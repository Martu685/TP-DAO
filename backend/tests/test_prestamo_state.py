import unittest

from src.prestamo_state import (
    InvalidPrestamoTransition,
    validate_initial_prestamo_state,
    validate_prestamo_transition,
)


class PrestamoStateTests(unittest.TestCase):
    def test_allows_valid_lifecycle_transitions(self):
        validate_prestamo_transition("Pendiente", "Activo")
        validate_prestamo_transition("ACTIVO", "Vencido")
        validate_prestamo_transition("Vencido", "Devuelto")
        validate_prestamo_transition("Pendiente", "Cancelado")

    def test_rejects_skipping_required_states(self):
        with self.assertRaises(InvalidPrestamoTransition):
            validate_prestamo_transition("Pendiente", "Devuelto")

    def test_accepts_only_open_initial_states(self):
        validate_initial_prestamo_state("Pendiente")
        validate_initial_prestamo_state("En curso")
        with self.assertRaises(InvalidPrestamoTransition):
            validate_initial_prestamo_state("Devuelto")

    def test_rejects_unconfigured_state_names(self):
        with self.assertRaises(ValueError):
            validate_prestamo_transition("Desconocido", "Activo")


if __name__ == "__main__":
    unittest.main()