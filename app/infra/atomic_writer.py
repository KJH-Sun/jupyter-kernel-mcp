"""Atomic file writing via temp file + os.replace."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.domain.errors import NotebookSaveError


def atomic_write(path: str | Path, content: str) -> None:
    """Write *content* to *path* atomically.

    Creates a temp file in the same directory, writes content, then
    replaces the target. This ensures the original file is never left
    in a partial state.
    """
    path = Path(path)
    parent = path.parent

    try:
        fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, path)
        except BaseException:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except NotebookSaveError:
        raise
    except Exception as exc:
        raise NotebookSaveError(f"Failed to save {path}: {exc}") from exc
