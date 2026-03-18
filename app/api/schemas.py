"""Pydantic request/response schemas for the FastAPI layer."""

from __future__ import annotations

from app.domain.models import (
    CellInfo,
    CellOutput,
    ExecutionMode,
    ExecutionResult,
    NotebookInfo,
    SessionInfo,
)
from pydantic import BaseModel, Field


# -- Requests --

class NotebookPathRequest(BaseModel):
    path: str = Field(..., description="Absolute or relative path to the .ipynb file")


class RunCellRequest(BaseModel):
    path: str
    cell_index: int = Field(..., ge=0, description="0-based cell index")
    mode: ExecutionMode = ExecutionMode.REUSE_EXISTING_SESSION
    timeout: float | None = Field(None, gt=0, description="Per-cell timeout in seconds")


class RunUntilRequest(BaseModel):
    path: str
    cell_index: int = Field(..., ge=0, description="Run all code cells up to and including this index")
    mode: ExecutionMode = ExecutionMode.RESTART_AND_RUN_UNTIL
    timeout: float | None = Field(None, gt=0)


class ShutdownIdleRequest(BaseModel):
    max_idle_seconds: float = Field(1800, gt=0)


# -- Responses --

class StatusResponse(BaseModel):
    status: str = "ok"
    message: str = ""


class RunCellResponse(BaseModel):
    status: str
    result: ExecutionResult


class RunUntilResponse(BaseModel):
    status: str
    results: list[ExecutionResult]


class ListCellsResponse(BaseModel):
    path: str
    cells: list[CellInfo]


class OpenNotebookResponse(BaseModel):
    status: str = "ok"
    notebook: NotebookInfo


class SessionsResponse(BaseModel):
    sessions: list[SessionInfo]


class ShutdownIdleResponse(BaseModel):
    status: str = "ok"
    shutdown_paths: list[str]


class RestartKernelResponse(BaseModel):
    status: str = "ok"
    session: SessionInfo
