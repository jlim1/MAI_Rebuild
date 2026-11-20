from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ask import ask_router
from .store import ROOT, Conflict, NotFound, Store


class Reservation(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(strict=True, gt=0, le=2**63 - 1)


class Advance(BaseModel):
    expected_status: Literal["reserved", "packed", "shipped", "delivered"]


def create_app(root: Path = ROOT, *, ask_env=None) -> FastAPI:
    store = Store(root)

    @asynccontextmanager
    async def lifespan(_app):
        store.initialize()
        yield

    app = FastAPI(title="Parcel Workbench", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.get("/api/inventory")
    def inventory(q: str = ""):
        return store.inventory(q)

    @app.exception_handler(Conflict)
    async def conflict(_request: Request, exc: Conflict):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(NotFound)
    async def not_found(_request: Request, exc: NotFound):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.post("/api/orders", status_code=201)
    def reserve(body: Reservation):
        return store.reserve(body.sku, body.quantity)

    @app.get("/api/orders/{id}")
    def lookup(id: str):
        return store.lookup(id)

    @app.post("/api/orders/{id}/advance")
    def advance(id: str, body: Advance):
        return store.advance(id, body.expected_status)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(ask_router(store, ask_env))
    dist = root / "frontend" / "dist"
    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")

    return app


app = create_app()
