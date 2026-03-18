"""Test that kernel state is reused across cell executions."""

from __future__ import annotations

from pathlib import Path

import nbformat

from app.domain.models import ExecutionMode
from app.services.notebook_runtime_service import NotebookRuntimeService


def test_session_reuse_preserves_state(sample_notebook: Path, service: NotebookRuntimeService):
    """Cell 1 sets x=10, cell 2 uses x — must succeed with same kernel."""
    service.open_notebook(str(sample_notebook))

    # Run cell 0: x = 10
    r0 = service.run_cell(str(sample_notebook), 0, mode=ExecutionMode.REUSE_EXISTING_SESSION)
    assert r0.success

    # Run cell 1: y = x + 5; print(y)
    r1 = service.run_cell(str(sample_notebook), 1, mode=ExecutionMode.REUSE_EXISTING_SESSION)
    assert r1.success

    # Check that output contains "15"
    text_outputs = [o.text for o in r1.outputs if o.text]
    assert any("15" in t for t in text_outputs), f"Expected '15' in outputs: {text_outputs}"


def test_session_reuse_across_multiple_cells(sample_notebook: Path, service: NotebookRuntimeService):
    """Running cells 0, 1, 2 sequentially must carry state through."""
    path = str(sample_notebook)
    service.open_notebook(path)

    for i in range(3):
        result = service.run_cell(path, i, mode=ExecutionMode.REUSE_EXISTING_SESSION)
        assert result.success, f"Cell {i} failed: {result.error_message}"

    # Cell 2 computes z = x * y = 10 * 15 = 150
    r2 = service.run_cell(path, 2, mode=ExecutionMode.REUSE_EXISTING_SESSION)
    assert r2.success
    # Check execute_result output
    result_outputs = [o for o in r2.outputs if o.output_type == "execute_result"]
    assert len(result_outputs) > 0


def test_different_notebooks_get_different_kernels(tmp_dir: Path, service: NotebookRuntimeService):
    """Two different notebooks must have independent kernel sessions."""
    from tests.conftest import make_notebook

    nb1 = make_notebook([("code", "shared_var = 'notebook1'")])
    nb2 = make_notebook([("code", "print(shared_var)")])  # would fail if sharing kernel

    path1 = tmp_dir / "nb1.ipynb"
    path2 = tmp_dir / "nb2.ipynb"
    nbformat.write(nb1, str(path1))
    nbformat.write(nb2, str(path2))

    service.open_notebook(str(path1))
    service.open_notebook(str(path2))

    r1 = service.run_cell(str(path1), 0)
    assert r1.success

    r2 = service.run_cell(str(path2), 0)
    # nb2's cell references shared_var which doesn't exist in its kernel
    assert not r2.success
