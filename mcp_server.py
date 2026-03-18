#!/usr/bin/env python3
"""MCP server for notebook execution — exposes notebook runtime as MCP tools."""

from __future__ import annotations

import logging
from typing import Any

from mcp import types
from mcp.server.fastmcp import FastMCP

from app.domain.errors import NotebookError
from app.domain.models import ExecutionMode
from app.services.notebook_runtime_service import NotebookRuntimeService

logging.basicConfig(level=logging.WARNING)

mcp = FastMCP(
    "notebook-runtime",
    instructions="""\
Notebook execution runtime for AI agents.

IMPORTANT — Inspecting image outputs:
- Cell outputs may contain images (matplotlib, seaborn, PIL, etc.) stored as base64 in the .ipynb file.
- You CANNOT read base64 image data directly. You MUST call `get_cell_output` to retrieve images.
- `get_cell_output` returns images inline — no extra file reading step needed.
- When a user asks to "analyze a chart", "show the plot", or "check the output", ALWAYS use `get_cell_output` first.
- Do NOT attempt to parse .ipynb JSON or decode base64 manually. Use the tool.
""",
)

_service = NotebookRuntimeService()


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok", **data}


def _err(msg: str) -> dict[str, Any]:
    return {"status": "error", "message": msg}


@mcp.tool()
def open_notebook(path: str) -> dict[str, Any]:
    """Open a notebook and start a kernel session.

    Args:
        path: Absolute path to the .ipynb file.
    """
    try:
        info = _service.open_notebook(path)
        return _ok({"notebook": info.model_dump()})
    except NotebookError as e:
        return _err(str(e))


@mcp.tool()
def list_cells(path: str) -> dict[str, Any]:
    """List all cells in a notebook with index, type, and source.

    Args:
        path: Absolute path to the .ipynb file.
    """
    try:
        cells = _service.list_cells(path)
        return _ok({"cells": [c.model_dump() for c in cells]})
    except NotebookError as e:
        return _err(str(e))


@mcp.tool()
def run_cell(
    path: str,
    cell_index: int,
    mode: str = "reuse_existing_session",
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run a single notebook cell by 0-based index.

    The cell must be a code cell. Outputs are persisted into the .ipynb file.
    If the cell produces image output (plots, charts), use `get_cell_output` afterwards to extract and view images.

    Args:
        path: Absolute path to the .ipynb file.
        cell_index: 0-based cell index.
        mode: "reuse_existing_session" (default) or "restart_and_run_until".
        timeout: Per-cell execution timeout in seconds (default 120).
    """
    try:
        result = _service.run_cell(
            path=path,
            cell_index=cell_index,
            mode=ExecutionMode(mode),
            timeout=timeout,
        )
        return _ok({"result": result.model_dump()})
    except NotebookError as e:
        return _err(str(e))


@mcp.tool()
def run_until(
    path: str,
    cell_index: int,
    mode: str = "restart_and_run_until",
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run all code cells from the beginning up to and including the target cell.

    If any cell produces image output (plots, charts), use `get_cell_output` afterwards to extract and view images.

    Args:
        path: Absolute path to the .ipynb file.
        cell_index: 0-based target cell index (inclusive).
        mode: "restart_and_run_until" (default) or "reuse_existing_session".
        timeout: Per-cell execution timeout in seconds.
    """
    try:
        results = _service.run_until(
            path=path,
            cell_index=cell_index,
            mode=ExecutionMode(mode),
            timeout=timeout,
        )
        all_ok = all(r.success for r in results)
        return {
            "status": "ok" if all_ok else "error",
            "results": [r.model_dump() for r in results],
        }
    except NotebookError as e:
        return _err(str(e))


@mcp.tool()
def restart_kernel(path: str) -> dict[str, Any]:
    """Restart the kernel for a notebook, clearing all execution state.

    Args:
        path: Absolute path to the .ipynb file.
    """
    try:
        session = _service.restart_kernel(path)
        return _ok({"session": session.model_dump()})
    except NotebookError as e:
        return _err(str(e))


@mcp.tool()
def list_sessions() -> dict[str, Any]:
    """List all active kernel sessions."""
    sessions = _service.list_sessions()
    return _ok({"sessions": [s.model_dump() for s in sessions]})


@mcp.tool()
def shutdown_idle(max_idle_seconds: float = 1800) -> dict[str, Any]:
    """Shutdown kernels that have been idle longer than the specified duration.

    Args:
        max_idle_seconds: Maximum idle time in seconds (default 1800 = 30 min).
    """
    paths = _service.shutdown_idle(max_idle_seconds)
    return _ok({"shutdown_paths": paths})


@mcp.tool()
def get_cell_output(path: str, cell_index: int) -> types.TextContent | list:
    """Read existing outputs from a cell. Images are returned inline — no extra step needed.

    Use this to inspect cell outputs — especially images (matplotlib charts, etc.)
    that are stored as base64 in the .ipynb file. Images are returned directly
    as image content so you can see them immediately.

    Args:
        path: Absolute path to the .ipynb file.
        cell_index: 0-based cell index.
    """
    try:
        result = _service.get_cell_output(path=path, cell_index=cell_index)
        content: list = []

        # Text summary of outputs
        text_data = {
            "status": "ok",
            "cell_index": result["cell_index"],
            "outputs": [o.model_dump() for o in result["outputs"]],
            "image_count": len(result["images"]),
        }
        content.append(types.TextContent(type="text", text=str(text_data)))

        # Inline images
        for img in result["images"]:
            content.append(types.ImageContent(
                type="image",
                data=img.data_b64,
                mimeType=img.mime_type,
            ))

        return content
    except NotebookError as e:
        return _err(str(e))


@mcp.tool()
def save_notebook(path: str) -> dict[str, Any]:
    """Explicitly save a notebook file.

    Args:
        path: Absolute path to the .ipynb file.
    """
    try:
        _service.save_notebook(path)
        return _ok({"message": f"Saved {path}"})
    except NotebookError as e:
        return _err(str(e))


if __name__ == "__main__":
    mcp.run()
