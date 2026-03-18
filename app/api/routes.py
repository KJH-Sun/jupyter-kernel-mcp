"""FastAPI route handlers — thin wrappers around NotebookRuntimeService."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ListCellsResponse,
    NotebookPathRequest,
    OpenNotebookResponse,
    RestartKernelResponse,
    RunCellRequest,
    RunCellResponse,
    RunUntilRequest,
    RunUntilResponse,
    SessionsResponse,
    ShutdownIdleRequest,
    ShutdownIdleResponse,
    StatusResponse,
)
from app.domain.errors import (
    CellIndexError,
    CellNotCodeError,
    KernelError,
    NotebookError,
    NotebookNotFoundError,
    UnsafePath,
)
from app.services.notebook_runtime_service import NotebookRuntimeService

router = APIRouter()

# Singleton service — created at app startup via lifespan
_service: NotebookRuntimeService | None = None


def get_service() -> NotebookRuntimeService:
    if _service is None:
        raise RuntimeError("Service not initialized")
    return _service


def set_service(svc: NotebookRuntimeService) -> None:
    global _service
    _service = svc


def _handle_error(exc: NotebookError) -> HTTPException:
    """Map domain errors to HTTP status codes."""
    if isinstance(exc, NotebookNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (CellIndexError, CellNotCodeError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, UnsafePath):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, KernelError):
        return HTTPException(status_code=500, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.post("/notebooks/open", response_model=OpenNotebookResponse)
def open_notebook(req: NotebookPathRequest):
    try:
        info = get_service().open_notebook(req.path)
        return OpenNotebookResponse(notebook=info)
    except NotebookError as exc:
        raise _handle_error(exc)


@router.get("/notebooks/cells", response_model=ListCellsResponse)
def list_cells(path: str):
    try:
        cells = get_service().list_cells(path)
        return ListCellsResponse(path=path, cells=cells)
    except NotebookError as exc:
        raise _handle_error(exc)


@router.post("/notebooks/run-cell", response_model=RunCellResponse)
def run_cell(req: RunCellRequest):
    try:
        result = get_service().run_cell(
            path=req.path,
            cell_index=req.cell_index,
            mode=req.mode,
            timeout=req.timeout,
        )
        return RunCellResponse(status="ok" if result.success else "error", result=result)
    except NotebookError as exc:
        raise _handle_error(exc)


@router.post("/notebooks/run-until", response_model=RunUntilResponse)
def run_until(req: RunUntilRequest):
    try:
        results = get_service().run_until(
            path=req.path,
            cell_index=req.cell_index,
            mode=req.mode,
            timeout=req.timeout,
        )
        all_ok = all(r.success for r in results)
        return RunUntilResponse(status="ok" if all_ok else "error", results=results)
    except NotebookError as exc:
        raise _handle_error(exc)


@router.post("/notebooks/restart-kernel", response_model=RestartKernelResponse)
def restart_kernel(req: NotebookPathRequest):
    try:
        session = get_service().restart_kernel(req.path)
        return RestartKernelResponse(session=session)
    except NotebookError as exc:
        raise _handle_error(exc)


@router.post("/notebooks/save", response_model=StatusResponse)
def save_notebook(req: NotebookPathRequest):
    try:
        get_service().save_notebook(req.path)
        return StatusResponse(message=f"Saved {req.path}")
    except NotebookError as exc:
        raise _handle_error(exc)


@router.get("/sessions", response_model=SessionsResponse)
def list_sessions():
    sessions = get_service().list_sessions()
    return SessionsResponse(sessions=sessions)


@router.post("/sessions/shutdown-idle", response_model=ShutdownIdleResponse)
def shutdown_idle(req: ShutdownIdleRequest | None = None):
    max_idle = req.max_idle_seconds if req else 1800
    paths = get_service().shutdown_idle(max_idle)
    return ShutdownIdleResponse(shutdown_paths=paths)
