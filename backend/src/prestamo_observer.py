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


class PrestamoObserver(Protocol):
    def update(self, event: PrestamoEstadoEvent, db) -> None:
        ...


class PrestamoSubject:
    def __init__(self):
        self._observers = []

    def attach(self, observer: PrestamoObserver):
        self._observers.append(observer)

    def notify(self, event: PrestamoEstadoEvent, db):
        for observer in self._observers:
            observer.update(event, db)


class NotificacionObserver:
    def update(self, event: PrestamoEstadoEvent, db):
        if event.socio_id is None:
            return

        db.add(
            NotificacionModel(
                fecha=datetime.now(),
                canal="sistema",
                mensaje=event.mensaje
                or (
                    f"El préstamo {event.prestamo_id} cambió de "
                    f"{event.estado_anterior} a {event.estado_nuevo}."
                ),
                socio_id=event.socio_id,
            )
        )


prestamo_subject = PrestamoSubject()
prestamo_subject.attach(NotificacionObserver())