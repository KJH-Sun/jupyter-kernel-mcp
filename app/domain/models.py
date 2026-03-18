"""Domain models for the notebook execution system."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionMode(str, enum.Enum):
    """How the runtime should handle kernel state before execution."""

    REUSE_EXISTING_SESSION = "reuse_existing_session"
    RESTART_AND_RUN_UNTIL = "restart_and_run_until"


class CellType(str, enum.Enum):
    CODE = "code"
    MARKDOWN = "markdown"
    RAW = "raw"


class CellInfo(BaseModel):
    """Lightweight view of a notebook cell."""

    index: int
    cell_type: CellType
    source: str
    execution_count: int | None = None
    has_outputs: bool = False


class CellOutput(BaseModel):
    """A single output entry from cell execution."""

    output_type: str
    text: str | None = None
    data: dict[str, Any] | None = None
    ename: str | None = None
    evalue: str | None = None
    traceback: list[str] | None = None


class ExecutionResult(BaseModel):
    """Result of executing one cell."""

    cell_index: int
    success: bool
    execution_count: int | None = None
    outputs: list[CellOutput] = Field(default_factory=list)
    error_message: str | None = None


class SessionInfo(BaseModel):
    """Information about an active kernel session."""

    notebook_path: str
    kernel_id: str
    kernel_name: str
    started_at: datetime
    last_activity: datetime
    execution_count: int = 0


class NotebookInfo(BaseModel):
    """Summary of an opened notebook."""

    path: str
    cell_count: int
    code_cell_count: int
    kernel_spec: str | None = None
