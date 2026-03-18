"""Test restart_and_run_until execution mode."""

from __future__ import annotations

from pathlib import Path

import nbformat

from app.domain.models import ExecutionMode
from app.services.notebook_runtime_service import NotebookRuntimeService


def test_restart_and_run_until_builds_state(sample_notebook: Path, service: NotebookRuntimeService):
    """restart_and_run_until should run all prior cells so cell 2 succeeds."""
    path = str(sample_notebook)
    service.open_notebook(path)

    # Directly run cell 2 with restart_and_run_until
    result = service.run_cell(path, 2, mode=ExecutionMode.RESTART_AND_RUN_UNTIL)
    assert result.success, f"Cell 2 should succeed: {result.error_message}"


def test_run_until_explicit(sample_notebook: Path, service: NotebookRuntimeService):
    """run_until should return results for each code cell up to target."""
    path = str(sample_notebook)
    service.open_notebook(path)

    results = service.run_until(path, 2, mode=ExecutionMode.RESTART_AND_RUN_UNTIL)
    assert len(results) == 3  # cells 0, 1, 2 are all code
    assert all(r.success for r in results)


def test_run_until_skips_markdown(mixed_notebook: Path, service: NotebookRuntimeService):
    """run_until should skip markdown cells and only run code cells."""
    path = str(mixed_notebook)
    service.open_notebook(path)

    # Run until cell index 3 (code: print(x))
    results = service.run_until(path, 3, mode=ExecutionMode.RESTART_AND_RUN_UNTIL)

    # Should have executed 2 code cells (indices 1 and 3)
    assert len(results) == 2
    assert all(r.success for r in results)


def test_restart_clears_state(sample_notebook: Path, service: NotebookRuntimeService):
    """After restart, old variables should be gone."""
    path = str(sample_notebook)
    service.open_notebook(path)

    # Build state
    service.run_cell(path, 0)

    # Restart kernel
    service.restart_kernel(path)

    # Now cell 1 (uses x) should fail because x is gone
    result = service.run_cell(path, 1, mode=ExecutionMode.REUSE_EXISTING_SESSION)
    assert not result.success


def test_run_until_stops_on_error(error_notebook: Path, service: NotebookRuntimeService):
    """run_until should stop when a cell errors."""
    path = str(error_notebook)
    service.open_notebook(path)

    results = service.run_until(path, 1, mode=ExecutionMode.RESTART_AND_RUN_UNTIL)

    # Cell 0 succeeds, cell 1 fails
    assert len(results) == 2
    assert results[0].success
    assert not results[1].success
