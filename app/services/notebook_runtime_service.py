"""Orchestrates notebook operations: open, run cells, restart, save."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.domain.errors import CellNotCodeError
from app.domain.models import (
    CellInfo,
    ExecutionMode,
    ExecutionResult,
    NotebookInfo,
    SessionInfo,
)
from app.infra.file_lock import FileLockRegistry
from app.infra.notebook_repository import NotebookRepository
from app.services.cell_executor import CellExecutor
from app.services.image_extractor import extract_cell_images
from app.services.kernel_session_registry import KernelSessionRegistry
from app.services.output_serializer import outputs_to_models, serialize_outputs

logger = logging.getLogger(__name__)


class NotebookRuntimeService:
    """High-level service that coordinates notebook execution workflows."""

    def __init__(
        self,
        repo: NotebookRepository | None = None,
        registry: KernelSessionRegistry | None = None,
        executor: CellExecutor | None = None,
        locks: FileLockRegistry | None = None,
    ) -> None:
        self.repo = repo or NotebookRepository()
        self.registry = registry or KernelSessionRegistry()
        self.executor = executor or CellExecutor()
        self.locks = locks or FileLockRegistry()

    # ------------------------------------------------------------------
    # Open / inspect
    # ------------------------------------------------------------------

    def open_notebook(self, path: str) -> NotebookInfo:
        """Open a notebook, ensure a kernel session exists, return info."""
        nb = self.repo.load(path)
        kernel_name = self.repo.get_kernel_spec_name(nb)
        self.registry.get_or_create(path, kernel_name=kernel_name)

        code_cells = sum(1 for c in nb.cells if c.cell_type == "code")
        return NotebookInfo(
            path=path,
            cell_count=len(nb.cells),
            code_cell_count=code_cells,
            kernel_spec=kernel_name,
        )

    def list_cells(self, path: str) -> list[CellInfo]:
        """List all cells in a notebook."""
        return self.repo.list_cells(path)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_cell(
        self,
        path: str,
        cell_index: int,
        mode: ExecutionMode = ExecutionMode.REUSE_EXISTING_SESSION,
        timeout: float | None = None,
    ) -> ExecutionResult:
        """Run a single cell and persist outputs."""
        lock = self.locks.get(path)
        with lock:
            nb = self.repo.load(path)
            kernel_name = self.repo.get_kernel_spec_name(nb)

            # Validate cell
            cell = self.repo.validate_code_cell(nb, cell_index)

            if mode == ExecutionMode.RESTART_AND_RUN_UNTIL:
                return self._restart_and_run_until(path, nb, cell_index, kernel_name, timeout)

            # Reuse existing session
            session = self.registry.get_or_create(path, kernel_name=kernel_name)
            return self._execute_and_persist(path, nb, cell_index, cell.source, session, timeout)

    def run_until(
        self,
        path: str,
        cell_index: int,
        mode: ExecutionMode = ExecutionMode.RESTART_AND_RUN_UNTIL,
        timeout: float | None = None,
    ) -> list[ExecutionResult]:
        """Run all code cells from the start up to and including *cell_index*."""
        lock = self.locks.get(path)
        with lock:
            nb = self.repo.load(path)
            kernel_name = self.repo.get_kernel_spec_name(nb)

            # Validate target exists
            self.repo.get_cell(nb, cell_index)

            if mode == ExecutionMode.RESTART_AND_RUN_UNTIL:
                session = self.registry.restart(path, kernel_name=kernel_name)
            else:
                session = self.registry.get_or_create(path, kernel_name=kernel_name)

            results: list[ExecutionResult] = []
            for i in range(cell_index + 1):
                cell = nb.cells[i]
                if cell.cell_type != "code":
                    continue
                result = self._execute_and_persist(path, nb, i, cell.source, session, timeout)
                results.append(result)
                if not result.success:
                    # Stop on error
                    break

            return results

    def _restart_and_run_until(self, path, nb, target_index, kernel_name, timeout):
        """Restart kernel then run all code cells up to target."""
        session = self.registry.restart(path, kernel_name=kernel_name)
        results: list[ExecutionResult] = []
        for i in range(target_index + 1):
            cell = nb.cells[i]
            if cell.cell_type != "code":
                continue
            result = self._execute_and_persist(path, nb, i, cell.source, session, timeout)
            results.append(result)
            if not result.success:
                break
        # Return only the last (target) result for run_cell
        return results[-1] if results else ExecutionResult(
            cell_index=target_index, success=True, outputs=[]
        )

    def _execute_and_persist(self, path, nb, index, code, session, timeout):
        """Execute code, persist outputs, save notebook."""
        messages, exec_count, success = self.executor.execute(session, code, timeout=timeout)
        outputs = serialize_outputs(messages)
        self.repo.update_cell_outputs(nb, index, outputs, exec_count)
        self.repo.save(path, nb)

        return ExecutionResult(
            cell_index=index,
            success=success,
            execution_count=exec_count,
            outputs=outputs_to_models(outputs),
            error_message=self._extract_error(outputs) if not success else None,
        )

    @staticmethod
    def _extract_error(outputs: list[dict]) -> str | None:
        for out in outputs:
            if out.get("output_type") == "error":
                return f"{out.get('ename', '')}: {out.get('evalue', '')}"
        return None

    # ------------------------------------------------------------------
    # Output inspection
    # ------------------------------------------------------------------

    def get_cell_output(self, path: str, cell_index: int) -> dict:
        """Read existing outputs from a cell and extract any images to disk.

        Returns a dict with ``outputs`` (raw output dicts) and
        ``image_paths`` (list of saved image file paths).
        """
        nb = self.repo.load(path)
        cell = self.repo.get_cell(nb, cell_index)
        raw_outputs: list[dict] = list(cell.get("outputs", []))
        image_paths = extract_cell_images(path, cell_index, raw_outputs)
        return {
            "cell_index": cell_index,
            "outputs": outputs_to_models(raw_outputs),
            "image_paths": image_paths,
        }

    # ------------------------------------------------------------------
    # Kernel management
    # ------------------------------------------------------------------

    def restart_kernel(self, path: str) -> SessionInfo:
        """Restart the kernel for a notebook."""
        nb = self.repo.load(path)
        kernel_name = self.repo.get_kernel_spec_name(nb)
        session = self.registry.restart(path, kernel_name=kernel_name)
        return self._session_to_info(path, session)

    def shutdown_kernel(self, path: str) -> None:
        """Shutdown the kernel for a notebook."""
        self.registry.shutdown(path)

    def shutdown_idle(self, max_idle_seconds: float = 1800) -> list[str]:
        """Shutdown idle kernels. Returns list of shut-down paths."""
        return self.registry.shutdown_idle(max_idle_seconds)

    def shutdown_all(self) -> None:
        """Shutdown all kernels."""
        self.registry.shutdown_all()

    # ------------------------------------------------------------------
    # Session info
    # ------------------------------------------------------------------

    def list_sessions(self) -> list[SessionInfo]:
        """Return info about all active sessions."""
        sessions = self.registry.list_sessions()
        return [self._session_to_info(path, s) for path, s in sessions.items()]

    def save_notebook(self, path: str) -> None:
        """Explicitly save the notebook (re-reads and writes atomically)."""
        lock = self.locks.get(path)
        with lock:
            nb = self.repo.load(path)
            self.repo.save(path, nb)

    @staticmethod
    def _session_to_info(path: str, session) -> SessionInfo:
        return SessionInfo(
            notebook_path=path,
            kernel_id=session.kernel_id,
            kernel_name=session.kernel_name,
            started_at=session.started_at,
            last_activity=session.last_activity,
            execution_count=session.execution_count,
        )
