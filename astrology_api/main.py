"""
Arquivo principal da aplicação AstroAPI.

Este arquivo é o ponto de entrada para a aplicação FastAPI e configura
os routers, middleware, e outras configurações globais.
"""
from dotenv import load_dotenv
load_dotenv()  # Must be first — app.db reads env vars at import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path

from app.api.natal_chart_router import router as natal_chart_router
from app.api.transit_router import router as transit_router
from app.api.svg_chart_router import router as svg_chart_router
from app.api.synastry_router import router as synastry_router
from app.api.progression_router import router as progression_router
from app.api.return_router import router as return_router
from app.api.direction_router import router as direction_router
from app.api.interpret_router import router as interpret_router
from app.api.rectification_router import router as rectification_router
from app.api.charts_router import router as charts_router
from app.db import create_tables

create_tables()

# Criar aplicação FastAPI
app = FastAPI(
    title="AstroAPI",
    description="API para cálculos astrológicos, mapas natais, trânsitos e interpretações.",
    version="1.0.0",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, definir origens específicas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Importar e incluir routers
app.include_router(natal_chart_router)
app.include_router(transit_router)
app.include_router(svg_chart_router)
app.include_router(synastry_router)
app.include_router(progression_router)
app.include_router(return_router)
app.include_router(direction_router)
app.include_router(interpret_router)
app.include_router(rectification_router)
app.include_router(charts_router)

# ── Serve frontend static files in production ──────────────────────────────
DIST_DIR = Path(__file__).parent / "dist"
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(DIST_DIR / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA catch-all: serve index.html for all non-API routes."""
        return FileResponse(DIST_DIR / "index.html")
else:
    @app.get("/")
    async def read_root():
        return {"message": "Bem-vindo à AstroAPI", "version": "1.0.0", "docs": "/docs"}
