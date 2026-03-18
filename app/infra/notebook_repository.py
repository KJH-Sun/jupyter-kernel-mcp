"""Notebook file I/O using nbformat."""

from __future__ import annotations

import os
from pathlib import Path

import nbformat
from nbformat import NotebookNode

from app.domain.errors import (
    CellIndexError,
    CellNotCodeError,
    NotebookNotFoundError,
    UnsafePath,
)
from app.domain.models import CellInfo, CellType
from app.infra.atomic_writer import atomic_write


# Optional: restrict notebooks to a base directory.
_ALLOWED_BASE: str | None = os.environ.get("NOTEBOOK_BASE_DIR")


def _validate_path(path: str) -> Path:
    """Resolve and validate a notebook path."""
    p = Path(path).resolve()
    if ".." in Path(path).parts:
        raise UnsafePath(path)
    if _ALLOWED_BASE:
        base = Path(_ALLOWED_BASE).resolve()
        if not str(p).startswith(str(base)):
            raise UnsafePath(path)
    return p


class NotebookRepository:
    """Loads, mutates, and atomically saves .ipynb files."""

    def load(self, path: str) -> NotebookNode:
        """Read and parse a notebook from disk."""
        p = _validate_path(path)
        if not p.exists():
            raise NotebookNotFoundError(path)
        return nbformat.read(str(p), as_version=4)

    def save(self, path: str, nb: NotebookNode) -> None:
        """Atomically write a notebook to disk."""
        p = _validate_path(path)
        content = nbformat.writes(nb)
        atomic_write(p, content)

    def list_cells(self, path: str) -> list[CellInfo]:
        """Return lightweight cell info for every cell in the notebook."""
        nb = self.load(path)
        result: list[CellInfo] = []
        for i, cell in enumerate(nb.cells):
            result.append(
                CellInfo(
                    index=i,
                    cell_type=CellType(cell.cell_type),
                    source=cell.source,
                    execution_count=cell.get("execution_count"),
                    has_outputs=bool(cell.get("outputs")),
                )
            )
        return result

    def get_cell(self, nb: NotebookNode, index: int) -> NotebookNode:
        """Return a single cell by index, raising on out-of-range."""
        if index < 0 or index >= len(nb.cells):
            raise CellIndexError(index, len(nb.cells))
        return nb.cells[index]

    def validate_code_cell(self, nb: NotebookNode, index: int) -> NotebookNode:
        """Get a cell and verify it is a code cell."""
        cell = self.get_cell(nb, index)
        if cell.cell_type != "code":
            raise CellNotCodeError(index, cell.cell_type)
        return cell

    def update_cell_outputs(
        self,
        nb: NotebookNode,
        index: int,
        outputs: list[dict],
        execution_count: int | None,
    ) -> None:
        """Replace a cell's outputs and execution count."""
        cell = self.get_cell(nb, index)
        # Convert plain dicts to NotebookNode so nbformat can serialize them
        cell["outputs"] = [nbformat.from_dict(o) for o in outputs]
        cell["execution_count"] = execution_count

    def get_kernel_spec_name(self, nb: NotebookNode) -> str:
        """Extract kernel spec name, defaulting to python3."""
        return nb.metadata.get("kernelspec", {}).get("name", "python3")
