from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from src.models import NotificacionModel


@dataclass(frozen=True)
class PrestamoEstadoEvent:
    prestamo_id: Optional[int]
    estado_anterior: str
    estado_nuevo: str
    socio_id: Optional[int]
    mensaje: Optional[str] = None


@dataclass(frozen=True)
class ReservaEstadoEvent:
    reserva_id: int
    estado_anterior: str
    estado_nuevo: str
    socio_id: Optional[int]
    mensaje: Optional[str] = None


EstadoEvent = PrestamoEstadoEvent | ReservaEstadoEvent


class EstadoObserver(Protocol):
    def update(self, event: EstadoEvent, db) -> None:
        ...


class EstadoSubject:
    def __init__(self):
        self._observers: list[EstadoObserver] = []

    def attach(self, observer: EstadoObserver):
        self._observers.append(observer)

    def notify(self, event: EstadoEvent, db):
        for observer in self._observers:
            observer.update(event, db)


class NotificacionObserver:
    def update(self, event: EstadoEvent, db):
        if event.socio_id is None:
            return

        if event.mensaje:
            message = event.mensaje
        elif isinstance(event, ReservaEstadoEvent):
            message = (
                f"La reserva #{event.reserva_id} cambió de "
                f"{event.estado_anterior} a {event.estado_nuevo}."
            )
        else:
            message = (
                f"El préstamo {event.prestamo_id} cambió de "
                f"{event.estado_anterior} a {event.estado_nuevo}."
            )
        db.add(
            NotificacionModel(
                fecha=datetime.now(),
                canal="sistema",
                mensaje=message,
                socio_id=event.socio_id,
            )
        )


estado_subject = EstadoSubject()
estado_subject.attach(NotificacionObserver())


def notify_reservation_state_change(
    reservation,
    previous_state: str,
    new_state: str,
    db,
) -> None:
    estado_subject.notify(
        ReservaEstadoEvent(
            reserva_id=reservation.id,
            estado_anterior=previous_state,
            estado_nuevo=new_state,
            socio_id=reservation.socio_id,
        ),
        db,
    )