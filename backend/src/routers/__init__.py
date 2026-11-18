from .sede import router as sede_router
from .socio import router as socio_router
from .reserva import router as reserva_router
from .prestamo import router as prestamo_router
from .prestamo_local import router as prestamo_local_router
from .prestamo_inter import router as prestamo_inter_router
from .remito import router as remito_router
from .detalle_remito import router as detalle_remito_router
from .multa import router as multa_router
from .devolucion import router as devolucion_router
from .libro import router as libro_router
from .ejemplar import router as ejemplar_router
from .notificacion import router as notificacion_router
from .estado import router as estado_router
from .historial import router as historial_router
from .reportes import router as reportes_router
from .usuario import router as usuario_router

__all__ = [
    "sede_router",
    "socio_router",
    "reserva_router",
    "prestamo_router",
    "prestamo_local_router",
    "prestamo_inter_router",
    "remito_router",
    "detalle_remito_router",
    "multa_router",
    "devolucion_router",
    "libro_router",
    "ejemplar_router",
    "notificacion_router",
    "estado_router",
    "historial_router",
    "reportes_router",
    "usuario_router",
]
