import unittest
from datetime import date
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
                side_effect=lambda *args: states[args[1].estado_remito_id],
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

    def test_incident_remit_can_be_received_without_removing_incidence(self):
        self.remit.estado_remito_id = self.incident.id
        self.remit.fecha_emision = date.today()
        self.loan = SimpleNamespace(
            id=5,
            estado=SimpleNamespace(descripcion="Devuelto"),
            fecha_devolucion=None,
            sede_destino_id=3,
            ejemplar=SimpleNamespace(sede_id=1),
        )
        incidence_record = SimpleNamespace(descripcion="Faltó un ejemplar")
        self.remit.incidencias = [incidence_record]
        query = SimpleNamespace(
            filter=lambda *_: SimpleNamespace(all=lambda: [self.loan])
        )
        db = SimpleNamespace(
            query=lambda *_: query,
            commit=lambda: None,
            refresh=lambda _: None,
        )
        with (
            patch.object(remito, "_get_remito", return_value=self.remit),
            patch.object(
                remito,
                "_get_remito_state",
                side_effect=lambda *args: (
                    self.received
                    if args[1].estado_remito_id == self.received.id
                    else self.incident
                ),
            ),
            patch.object(
                remito,
                "get_status_by_name",
                side_effect=lambda *args: (
                    self.received
                    if args[2] == "Recibido"
                    else SimpleNamespace(id=4)
                ),
            ),
            patch.object(remito, "require_active_branch"),
            patch.object(remito, "release_exemplar_to_reservation"),
        ):
            result = remito.receive_remito(self.remit.id, db)

        self.assertEqual(result.estado_remito_id, self.received.id)
        self.assertEqual(result.fecha_recepcion, date.today())
        self.assertEqual(result.incidencias, [incidence_record])

    def test_only_prepared_remit_can_be_cancelled(self):
        prepared = SimpleNamespace(id=4, descripcion="Preparado")
        cancelled = SimpleNamespace(id=5, descripcion="Cancelado")
        self.remit.estado_remito_id = prepared.id
        loan = SimpleNamespace(remito_id=self.remit.id)
        query = SimpleNamespace(
            filter=lambda *_: SimpleNamespace(all=lambda: [loan])
        )
        db = SimpleNamespace(
            query=lambda *_: query,
            commit=lambda: None,
            refresh=lambda _: None,
        )
        with (
            patch.object(remito, "_get_remito", return_value=self.remit),
            patch.object(remito, "_get_remito_state", return_value=prepared),
            patch.object(remito, "get_status_by_name", return_value=cancelled),
        ):
            result = remito.cancel_remito(self.remit.id, db)

        self.assertEqual(result.estado_remito_id, cancelled.id)
        self.assertIsNone(loan.remito_id)

        with (
            patch.object(remito, "_get_remito", return_value=self.remit),
            patch.object(remito, "_get_remito_state", return_value=cancelled),
        ):
            with self.assertRaises(HTTPException) as error:
                remito.cancel_remito(self.remit.id, db)

        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
