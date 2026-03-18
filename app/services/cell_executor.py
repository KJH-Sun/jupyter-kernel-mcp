"""Executes code cells on a live Jupyter kernel and collects outputs."""

from __future__ import annotations

import logging
from typing import Any

from app.domain.errors import KernelExecutionTimeoutError
from app.services.kernel_session_registry import KernelSession

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120  # seconds


class CellExecutor:
    """Sends execute requests to a kernel and collects IOPub messages."""

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def execute(
        self,
        session: KernelSession,
        code: str,
        timeout: float | None = None,
    ) -> tuple[list[dict[str, Any]], int | None, bool]:
        """Execute *code* on *session*'s kernel.

        Returns:
            (messages, execution_count, success)
            - messages: raw IOPub message dicts relevant to output
            - execution_count: from execute_reply
            - success: True if status is 'ok'
        """
        kc = session.kernel_client  # type: ignore[attr-defined]
        timeout = timeout or self.timeout

        msg_id = kc.execute(code)
        session.touch()

        messages: list[dict[str, Any]] = []
        execution_count: int | None = None
        success = True

        # Collect IOPub messages until kernel returns to idle
        while True:
            try:
                msg = kc.get_iopub_msg(timeout=timeout)
            except Exception:
                raise KernelExecutionTimeoutError(timeout)

            # Only process messages for our request
            parent_id = msg.get("parent_header", {}).get("msg_id")
            if parent_id != msg_id:
                continue

            msg_type = msg.get("msg_type") or msg.get("header", {}).get("msg_type", "")

            if msg_type == "status":
                state = msg.get("content", {}).get("execution_state")
                if state == "idle":
                    break
                continue

            if msg_type == "execute_input":
                execution_count = msg.get("content", {}).get("execution_count")
                continue

            # Collect output-producing messages
            if msg_type in ("stream", "execute_result", "display_data", "error"):
                messages.append(msg)
                if msg_type == "error":
                    success = False
                if msg_type == "execute_result":
                    execution_count = msg.get("content", {}).get("execution_count", execution_count)

        # Also check the shell reply for execution_count
        try:
            reply = kc.get_shell_msg(timeout=10)
            reply_content = reply.get("content", {})
            if reply_content.get("execution_count"):
                execution_count = reply_content["execution_count"]
            if reply_content.get("status") == "error":
                success = False
        except Exception:
            logger.warning("Could not get shell reply for msg_id=%s", msg_id)

        session.execution_count = execution_count or (session.execution_count + 1)
        return messages, execution_count, success
