"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router, set_service
from app.services.notebook_runtime_service import NotebookRuntimeService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

_service: NotebookRuntimeService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _service
    _service = NotebookRuntimeService()
    set_service(_service)
    logging.getLogger(__name__).info("Notebook runtime service started")
    yield
    _service.shutdown_all()
    logging.getLogger(__name__).info("All kernels shut down")


app = FastAPI(
    title="Notebook Execution Service",
    description="Stateful notebook execution runtime for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
