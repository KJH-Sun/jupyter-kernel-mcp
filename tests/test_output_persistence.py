"""Test that execution outputs are persisted into the .ipynb file."""

from __future__ import annotations

from pathlib import Path

import nbformat

from app.services.notebook_runtime_service import NotebookRuntimeService


def test_outputs_saved_to_notebook_file(sample_notebook: Path, service: NotebookRuntimeService):
    """After execution, re-reading the notebook must show outputs."""
    path = str(sample_notebook)
    service.open_notebook(path)
    service.run_cell(path, 0)
    service.run_cell(path, 1)

    # Re-read from disk
    nb = nbformat.read(path, as_version=4)
    cell1 = nb.cells[1]
    assert len(cell1.outputs) > 0, "Cell 1 should have outputs after execution"

    # Check that stream output contains "15"
    stream_texts = [o.get("text", "") for o in cell1.outputs if o.get("output_type") == "stream"]
    assert any("15" in t for t in stream_texts), f"Expected '15' in stream outputs: {stream_texts}"


def test_execution_count_persisted(sample_notebook: Path, service: NotebookRuntimeService):
    """execution_count should be set on executed cells."""
    path = str(sample_notebook)
    service.open_notebook(path)
    service.run_cell(path, 0)

    nb = nbformat.read(path, as_version=4)
    assert nb.cells[0].execution_count is not None
    assert nb.cells[0].execution_count >= 1


def test_error_output_persisted(error_notebook: Path, service: NotebookRuntimeService):
    """When a cell throws, the error must be persisted in the notebook."""
    path = str(error_notebook)
    service.open_notebook(path)
    service.run_cell(path, 0)
    result = service.run_cell(path, 1)

    assert not result.success

    # Check disk
    nb = nbformat.read(path, as_version=4)
    cell1 = nb.cells[1]
    error_outputs = [o for o in cell1.outputs if o.get("output_type") == "error"]
    assert len(error_outputs) > 0, "Error output should be persisted"
    assert error_outputs[0]["ename"] == "NameError"


def test_atomic_save_does_not_corrupt(sample_notebook: Path, service: NotebookRuntimeService):
    """After save, the notebook must still be valid nbformat."""
    path = str(sample_notebook)
    service.open_notebook(path)
    service.run_cell(path, 0)

    # Should not raise
    nb = nbformat.read(path, as_version=4)
    nbformat.validate(nb)
