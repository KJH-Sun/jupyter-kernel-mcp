#!/usr/bin/env python3
"""CLI for AI-agent notebook execution.

Directly imports the service layer — no running HTTP server required.
All output is structured JSON for machine consumption.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.domain.errors import NotebookError
from app.domain.models import ExecutionMode
from app.services.notebook_runtime_service import NotebookRuntimeService

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# Module-level singleton, created lazily
_service: NotebookRuntimeService | None = None


def _get_service() -> NotebookRuntimeService:
    global _service
    if _service is None:
        _service = NotebookRuntimeService()
    return _service


def _output(data: dict) -> None:
    """Print JSON to stdout."""
    click.echo(json.dumps(data, indent=2, default=str))


def _error_output(msg: str, code: str = "error") -> None:
    _output({"status": "error", "error_code": code, "message": msg})
    sys.exit(1)


@click.group()
def cli():
    """Notebook execution agent CLI. All commands output JSON."""
    pass


@cli.command()
@click.option("--path", required=True, help="Path to .ipynb file")
def open(path: str):
    """Open a notebook and start a kernel session."""
    try:
        info = _get_service().open_notebook(path)
        _output({"status": "ok", "notebook": info.model_dump()})
    except NotebookError as exc:
        _error_output(str(exc))


@cli.command("list-cells")
@click.option("--path", required=True, help="Path to .ipynb file")
def list_cells(path: str):
    """List all cells in a notebook."""
    try:
        cells = _get_service().list_cells(path)
        _output({
            "status": "ok",
            "path": path,
            "cells": [c.model_dump() for c in cells],
        })
    except NotebookError as exc:
        _error_output(str(exc))


@cli.command("run-cell")
@click.option("--path", required=True, help="Path to .ipynb file")
@click.option("--cell", required=True, type=int, help="0-based cell index")
@click.option(
    "--mode",
    default="reuse_existing_session",
    type=click.Choice(["reuse_existing_session", "restart_and_run_until"]),
    help="Execution mode",
)
@click.option("--timeout", default=None, type=float, help="Timeout in seconds")
def run_cell(path: str, cell: int, mode: str, timeout: float | None):
    """Run a single cell."""
    try:
        result = _get_service().run_cell(
            path=path,
            cell_index=cell,
            mode=ExecutionMode(mode),
            timeout=timeout,
        )
        _output({
            "status": "ok" if result.success else "error",
            "result": result.model_dump(),
        })
    except NotebookError as exc:
        _error_output(str(exc))


@cli.command("run-until")
@click.option("--path", required=True, help="Path to .ipynb file")
@click.option("--cell", required=True, type=int, help="Run all code cells up to this 0-based index")
@click.option(
    "--mode",
    default="restart_and_run_until",
    type=click.Choice(["reuse_existing_session", "restart_and_run_until"]),
    help="Execution mode",
)
@click.option("--timeout", default=None, type=float, help="Per-cell timeout in seconds")
def run_until(path: str, cell: int, mode: str, timeout: float | None):
    """Run all code cells from start up to and including the target cell."""
    try:
        results = _get_service().run_until(
            path=path,
            cell_index=cell,
            mode=ExecutionMode(mode),
            timeout=timeout,
        )
        all_ok = all(r.success for r in results)
        _output({
            "status": "ok" if all_ok else "error",
            "results": [r.model_dump() for r in results],
        })
    except NotebookError as exc:
        _error_output(str(exc))


@cli.command("get-cell-output")
@click.option("--path", required=True, help="Path to .ipynb file")
@click.option("--cell", required=True, type=int, help="0-based cell index")
def get_cell_output(path: str, cell: int):
    """Read existing outputs from a cell and extract images to temp files."""
    try:
        result = _get_service().get_cell_output(path=path, cell_index=cell)
        _output({
            "status": "ok",
            "cell_index": result["cell_index"],
            "outputs": [o.model_dump() for o in result["outputs"]],
            "image_paths": result["image_paths"],
        })
    except NotebookError as exc:
        _error_output(str(exc))


@cli.command("restart-kernel")
@click.option("--path", required=True, help="Path to .ipynb file")
def restart_kernel(path: str):
    """Restart the kernel for a notebook."""
    try:
        session = _get_service().restart_kernel(path)
        _output({"status": "ok", "session": session.model_dump()})
    except NotebookError as exc:
        _error_output(str(exc))


@cli.command()
def sessions():
    """List all active kernel sessions."""
    sessions_list = _get_service().list_sessions()
    _output({
        "status": "ok",
        "sessions": [s.model_dump() for s in sessions_list],
    })


@cli.command("shutdown-idle")
@click.option("--max-idle", default=1800, type=float, help="Max idle seconds (default 1800)")
def shutdown_idle(max_idle: float):
    """Shutdown kernels idle longer than max-idle seconds."""
    paths = _get_service().shutdown_idle(max_idle)
    _output({"status": "ok", "shutdown_paths": paths})


@cli.command()
@click.option("--path", required=True, help="Path to .ipynb file")
def save(path: str):
    """Explicitly save a notebook."""
    try:
        _get_service().save_notebook(path)
        _output({"status": "ok", "message": f"Saved {path}"})
    except NotebookError as exc:
        _error_output(str(exc))


if __name__ == "__main__":
    cli()
