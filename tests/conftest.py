"""Shared fixtures for notebook execution tests."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import nbformat
import pytest

from app.services.notebook_runtime_service import NotebookRuntimeService


def make_notebook(cells: list[tuple[str, str]], kernel: str = "python3") -> nbformat.NotebookNode:
    """Create a notebook with given cells.

    Args:
        cells: list of (cell_type, source) tuples
        kernel: kernel spec name
    """
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": kernel, "display_name": "Python 3"}
    for cell_type, source in cells:
        if cell_type == "code":
            nb.cells.append(nbformat.v4.new_code_cell(source=source))
        elif cell_type == "markdown":
            nb.cells.append(nbformat.v4.new_markdown_cell(source=source))
        else:
            nb.cells.append(nbformat.v4.new_raw_cell(source=source))
    return nb


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory, cleaned up after test."""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_notebook(tmp_dir: Path) -> Path:
    """Create a simple 3-cell notebook for testing."""
    nb = make_notebook([
        ("code", "x = 10"),
        ("code", "y = x + 5\nprint(y)"),
        ("code", "z = x * y\nz"),
    ])
    path = tmp_dir / "test_notebook.ipynb"
    nbformat.write(nb, str(path))
    return path


@pytest.fixture
def error_notebook(tmp_dir: Path) -> Path:
    """Notebook where cell 1 depends on undefined variable."""
    nb = make_notebook([
        ("code", "a = 1"),
        ("code", "print(undefined_var)"),
    ])
    path = tmp_dir / "error_notebook.ipynb"
    nbformat.write(nb, str(path))
    return path


@pytest.fixture
def mixed_notebook(tmp_dir: Path) -> Path:
    """Notebook with markdown and code cells."""
    nb = make_notebook([
        ("markdown", "# Title"),
        ("code", "x = 42"),
        ("markdown", "## Section"),
        ("code", "print(x)"),
    ])
    path = tmp_dir / "mixed_notebook.ipynb"
    nbformat.write(nb, str(path))
    return path


@pytest.fixture
def service():
    """Provide a NotebookRuntimeService, shutdown kernels after test."""
    svc = NotebookRuntimeService()
    yield svc
    svc.shutdown_all()
