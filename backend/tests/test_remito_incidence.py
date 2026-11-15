import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from src.routers import remito


class RemitoIncidenceTests(unittest.TestCase):
    def setUp(self):
        self.transit = SimpleNamespace(id=1, descripcion="En tránsito")
        self.incident = SimpleNamespace(id=2, descripcion="Incidencia")
        self.received = SimpleNamespace(id=3, descripcion="Recibido")
        self.remit = SimpleNamespace(id=7, estado_remito_id=self.transit.id)
        self.db = SimpleNamespace(add=lambda _: None, commit=lambda: None, refresh=lambda _: None)

    def test_allows_one_incidence_and_rejects_another(self):
        states = {
            self.transit.id: self.transit,
            self.incident.id: self.incident,
        }

        with (
            patch.object(remito, "_get_remito", return_value=self.remit),
            patch.object(
                remito,
                "_get_remito_state",
                side_effect=lambda _db, current: states[current.estado_remito_id],
            ),
            patch.object(
                remito,
                "get_status_by_name",
                return_value=self.incident,
            ),
        ):
            first = remito.create_remito_incidence(
                self.remit.id, remito.IncidenciaSchema(descripcion="Incidencia 1"), self.db
            )
            with self.assertRaises(HTTPException) as error:
                remito.create_remito_incidence(
                    self.remit.id,
                    remito.IncidenciaSchema(descripcion="Incidencia 2"),
                    self.db,
                )

        self.assertEqual(first.descripcion, "Incidencia 1")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(
            error.exception.detail,
            "El remito ya tiene una incidencia registrada",
        )
        self.assertEqual(self.remit.estado_remito_id, self.incident.id)

    def test_rejects_incidence_after_remit_is_received(self):
        self.remit.estado_remito_id = self.received.id
        with (
            patch.object(remito, "_get_remito", return_value=self.remit),
            patch.object(remito, "_get_remito_state", return_value=self.received),
        ):
            with self.assertRaises(HTTPException) as error:
                remito.create_remito_incidence(
                    self.remit.id,
                    remito.IncidenciaSchema(descripcion="Fuera de tránsito"),
                    self.db,
                )

        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
