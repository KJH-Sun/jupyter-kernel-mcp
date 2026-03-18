"""Convert Jupyter kernel IOPub messages into notebook-compatible output dicts."""

from __future__ import annotations

from typing import Any

from app.domain.models import CellOutput


def _msg_to_output(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a single kernel message to a nbformat output dict.

    Returns None for messages that don't map to outputs.
    """
    msg_type = msg.get("msg_type") or msg.get("header", {}).get("msg_type", "")
    content = msg.get("content", {})

    if msg_type == "stream":
        return {
            "output_type": "stream",
            "name": content.get("name", "stdout"),
            "text": content.get("text", ""),
        }

    if msg_type == "execute_result":
        return {
            "output_type": "execute_result",
            "execution_count": content.get("execution_count"),
            "data": content.get("data", {}),
            "metadata": content.get("metadata", {}),
        }

    if msg_type == "display_data":
        return {
            "output_type": "display_data",
            "data": content.get("data", {}),
            "metadata": content.get("metadata", {}),
        }

    if msg_type == "error":
        return {
            "output_type": "error",
            "ename": content.get("ename", ""),
            "evalue": content.get("evalue", ""),
            "traceback": content.get("traceback", []),
        }

    return None


def serialize_outputs(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a list of kernel IOPub messages to notebook output dicts."""
    outputs: list[dict[str, Any]] = []
    for msg in messages:
        out = _msg_to_output(msg)
        if out is not None:
            outputs.append(out)
    return outputs


def outputs_to_models(outputs: list[dict[str, Any]]) -> list[CellOutput]:
    """Convert notebook output dicts to CellOutput pydantic models."""
    result: list[CellOutput] = []
    for out in outputs:
        result.append(
            CellOutput(
                output_type=out["output_type"],
                text=out.get("text"),
                data=out.get("data"),
                ename=out.get("ename"),
                evalue=out.get("evalue"),
                traceback=out.get("traceback"),
            )
        )
    return result
