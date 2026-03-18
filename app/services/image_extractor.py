"""Extract image data from notebook cell outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_IMAGE_MIME_TYPES = ("image/png", "image/jpeg")


@dataclass
class CellImage:
    """A single image extracted from cell output."""

    mime_type: str
    data_b64: str  # base64-encoded image data (ready for MCP ImageContent)


def extract_cell_images(outputs: list[dict]) -> list[CellImage]:
    """Extract base64-encoded images from cell outputs.

    Returns a list of CellImage (empty if no images found).
    The data_b64 field contains clean base64 ready for MCP ImageContent.
    """
    images: list[CellImage] = []

    for output in outputs:
        data = output.get("data", {})
        for mime in _IMAGE_MIME_TYPES:
            if mime not in data:
                continue
            raw = data[mime]
            if not isinstance(raw, str):
                continue
            # nbformat may store base64 with embedded newlines — strip them
            clean_b64 = raw.replace("\n", "")
            images.append(CellImage(mime_type=mime, data_b64=clean_b64))
            logger.debug("Extracted %s image from cell output", mime)

    return images
