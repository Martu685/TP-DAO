# Sistema de gestión de biblioteca

Aplicación de escritorio/web con una API REST para administrar libros, ejemplares, socios, sedes, préstamos, reservas y remitos. El backend usa FastAPI y SQLAlchemy; la interfaz está hecha con Flet.

## Requisitos

- Python 3.10 o superior.
- `pip`.

## Instalación en Windows (PowerShell)

Desde la carpeta raíz del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install -r frontend\requirements.txt
```

Si PowerShell bloquea la activación del entorno, podés ejecutar los comandos de instalación usando `.\.venv\Scripts\python.exe -m pip ...` y luego iniciar la aplicación con ese mismo `python.exe`.

## Iniciar la aplicación

Necesitás dos terminales, ambas con el entorno virtual activado.

En la primera, iniciá la API:

```powershell
cd backend
python -m uvicorn src.main:app --reload
```

La API queda disponible en `http://127.0.0.1:8000`. La documentación interactiva está en `http://127.0.0.1:8000/docs`.

En la segunda terminal, desde la carpeta raíz del proyecto, iniciá la interfaz:

```powershell
python -m frontend
```

Flet abre la aplicación en el navegador. Por defecto, la interfaz se conecta a `http://127.0.0.1:8000`. Para usar otra URL, definí `BIBLIOTECA_API_URL` antes de iniciar el frontend:

```powershell
$env:BIBLIOTECA_API_URL = "http://127.0.0.1:8000"
python -m frontend
```

## Base de datos

Por defecto, el backend crea una base SQLite llamada `biblioteca.db` en la carpeta desde donde se inicia Uvicorn. Al seguir los comandos anteriores, queda en `backend/biblioteca.db`. Las tablas y los estados iniciales se crean automáticamente al iniciar la API.

Para usar otra base, configurá `DATABASE_URL` antes de iniciar el backend. Por ejemplo, SQLite con una ruta explícita:

```powershell
$env:DATABASE_URL = "sqlite:///./biblioteca.db"
```

También se puede configurar la conexión de PostgreSQL con una URL SQLAlchemy y el controlador correspondiente instalado.

## Usuario administrador

El backend no crea una cuenta administrador si no se configura. Para crearla al iniciar, definí estas dos variables de entorno. La contraseña debe tener al menos 8 caracteres:

```powershell
$env:BIBLIOTECA_ADMIN_EMAIL = "admin@biblioteca.local"
$env:BIBLIOTECA_ADMIN_PASSWORD = "cambiar-esta-clave"
cd backend
python -m uvicorn src.main:app --reload
```

También podés guardar esas variables en `backend/.env` (ese archivo está excluido de Git). Si no configurás un administrador, se puede registrar una cuenta de socio desde la pantalla de acceso; para las funciones de gestión se necesita un usuario con rol de bibliotecario o administrador.

## Detener

En cada terminal, presioná `Ctrl+C`. Para salir del entorno virtual, ejecutá `deactivate`.
