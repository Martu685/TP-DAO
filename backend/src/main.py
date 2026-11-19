from fastapi import FastAPI
from src.database import engine, Base, ensure_user_branch_column
from src.bootstrap import initialize_admin_account, initialize_reference_data
from src.routers import (
    sede_router,
    socio_router,
    reserva_router,
    prestamo_router,
    prestamo_local_router,
    prestamo_inter_router,
    remito_router,
    detalle_remito_router,
    multa_router,
    devolucion_router,
    libro_router,
    ejemplar_router,
    notificacion_router,
    estado_router,
    historial_router,
    reportes_router,
    usuario_router,
)

Base.metadata.create_all(bind=engine)
ensure_user_branch_column()
initialize_reference_data()
initialize_admin_account()

app = FastAPI(
    title="Sistema de Gestion de Biblioteca - UTN FRC",
    description="API RESTful completa mapeada al Diagrama de Clases UML.",
    version="1.0.0",
)

app.include_router(sede_router)
app.include_router(socio_router)
app.include_router(reserva_router)
app.include_router(prestamo_router)
app.include_router(prestamo_local_router)
app.include_router(prestamo_inter_router)
app.include_router(remito_router)
app.include_router(detalle_remito_router)
app.include_router(multa_router)
app.include_router(devolucion_router)
app.include_router(libro_router)
app.include_router(ejemplar_router)
app.include_router(notificacion_router)
app.include_router(estado_router)
app.include_router(historial_router)
app.include_router(reportes_router)
app.include_router(usuario_router)

@app.get("/", tags=["Root"])
def root():
    return {"message": "API de Biblioteca activa con mapeo completo UML", "docs": "/docs"}
