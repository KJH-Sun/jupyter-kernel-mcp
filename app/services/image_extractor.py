"""Extract image outputs from notebook cell data and save to temp files."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_IMAGE_MIME_TYPES = ("image/png", "image/jpeg")
_MIME_EXT = {"image/png": ".png", "image/jpeg": ".jpg"}
_BASE_DIR = Path("/tmp/notebook-agent")


def extract_cell_images(
    notebook_path: str,
    cell_index: int,
    outputs: list[dict],
) -> list[str]:
    """Extract base64-encoded images from cell outputs and save to disk.

    Returns a list of saved file paths (empty if no images found).
    """
    notebook_stem = Path(notebook_path).stem
    dest_dir = _BASE_DIR / notebook_stem
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    img_counter = 0

    for output in outputs:
        data = output.get("data", {})
        for mime in _IMAGE_MIME_TYPES:
            if mime not in data:
                continue
            raw = data[mime]
            # nbformat stores base64 as a string (possibly with newlines)
            if isinstance(raw, str):
                img_bytes = base64.b64decode(raw)
            elif isinstance(raw, bytes):
                img_bytes = raw
            else:
                continue

            ext = _MIME_EXT[mime]
            filename = f"cell_{cell_index}_{img_counter}{ext}"
            filepath = dest_dir / filename
            filepath.write_bytes(img_bytes)

            saved.append(str(filepath))
            img_counter += 1
            logger.debug("Saved image: %s", filepath)

    return saved
