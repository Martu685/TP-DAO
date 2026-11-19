# Frontend Flet

Interfaz de escritorio/web para el sistema de gestión de biblioteca. Se conecta a la API FastAPI existente.

## Ejecución

Desde la raíz del repositorio, instalá las dependencias y levantá el backend:

```powershell
python -m pip install -r frontend\requirements.txt
cd backend
python -m uvicorn src.main:app --reload
```

Si el backend ya está ejecutándose en el mismo entorno virtual, detenelo antes de instalar las dependencias para que Windows pueda actualizar FastAPI.

En otra terminal, desde la raíz:

```powershell
python -m frontend
```

La app se abre en el navegador usando el modo web de Flet. Las dependencias limitan FastAPI a una versión compatible con Flet Web. La interfaz usa `http://127.0.0.1:8000` como URL de API por defecto. Para apuntar a otra instancia, configurá `BIBLIOTECA_API_URL` antes de iniciar la app.

Incluye un resumen de actividad y pantallas para consultar libros, socios, historial de lecturas, sedes, ejemplares, remitos y préstamos, registrar y editar libros, socios y sedes, crear remitos, despacharlos y recibirlos, gestionar incidencias, crear préstamos locales, administrar devoluciones y multas vinculadas a préstamos, gestionar el acceso de usuarios y consultar reportes.

## Acceso y usuarios

Al iniciar la app aparece el formulario de acceso, con la opción de registrarse como socio. La sesión se mantiene solo en memoria y puede cerrarse desde el botón **Cerrar sesión**. Los socios pueden consultar su historial de lecturas, sus préstamos locales y las notificaciones asociadas a sus préstamos. Bibliotecarios y administradores acceden a las vistas de gestión; la vista **Usuarios** requiere una sesión de administrador. Los cambios de estado de los préstamos generan notificaciones automáticamente. Si todavía no hay una cuenta administradora, configurá `BIBLIOTECA_ADMIN_EMAIL` y `BIBLIOTECA_ADMIN_PASSWORD` al iniciar el backend.
