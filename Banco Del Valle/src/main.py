"""
Punto de entrada principal del servidor FastAPI (Backend Core Bancario).
Configura middlewares CORS, ciclo de vida lifespan y montaje de routers HTTP/WS.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router_dashboard import router as router_dashboard
from src.api.router_scoring import router as router_scoring
from src.api.websocket_sim import detener_tarea_simulacion, router as router_websocket
from src.database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida del servidor: inicializa base de datos y libera tareas de simulación."""
    # Inicialización de tablas y siembra de demostración
    init_db(seed_demo=True)
    yield
    # Limpieza al apagar el servidor
    detener_tarea_simulacion()


app = FastAPI(
    title="Banco del Valle — Scoring Calculator & Lending Engine API",
    description="Motor de Evaluación Crediticia Francesa, Solvencia Patrimonial BCRA y Simulación Temporal.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configuración de CORS para permitir la conexión desde Vite/React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montaje de módulos de endpoints
app.include_router(router_scoring)
app.include_router(router_dashboard)
app.include_router(router_websocket)


import os
from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Ruta de distribución compilada de frontend Vite
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
assets_dir = os.path.join(frontend_dist, "assets")

if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def estado_servidor(request: Request):
    """Endpoint raíz: entrega la SPA si es un navegador web o JSON de salud."""
    accept = request.headers.get("accept", "")
    index_file = os.path.join(frontend_dist, "index.html")
    if "text/html" in accept and os.path.isfile(index_file):
        return FileResponse(index_file)
    return {
        "entidad": "Banco del Valle — San Fernando del Valle de Catamarca",
        "estado": "ONLINE",
        "normativa": "Regulación BCRA / UIF",
        "docs_swagger": "/docs",
        "version": "1.0.0",
    }


@app.get("/{full_path:path}")
async def catch_all_spa(request: Request, full_path: str):
    """Fallback para navegación en cliente (SPA React Router) y recursos estáticos."""
    accept = request.headers.get("accept", "")
    static_file = os.path.join(frontend_dist, full_path)
    if os.path.isfile(static_file):
        return FileResponse(static_file)
    index_file = os.path.join(frontend_dist, "index.html")
    if "text/html" in accept and os.path.isfile(index_file):
        return FileResponse(index_file)
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Ruta no encontrada")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
