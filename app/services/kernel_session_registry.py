"""Manages mapping from notebook paths to live Jupyter kernel sessions."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from jupyter_client.manager import KernelManager

from app.domain.errors import KernelError, KernelStartupError

logger = logging.getLogger(__name__)

_STARTUP_TIMEOUT = 60  # seconds


@dataclass
class KernelSession:
    """A live kernel session bound to a notebook path."""

    kernel_manager: KernelManager
    kernel_client: object  # KernelClient
    kernel_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_count: int = 0

    @property
    def kernel_id(self) -> str:
        return self.kernel_manager.kernel_id or "unknown"

    def touch(self) -> None:
        """Update last_activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)


class KernelSessionRegistry:
    """Thread-safe registry of per-notebook kernel sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, KernelSession] = {}
        self._lock = threading.Lock()

    def _resolve_key(self, path: str) -> str:
        return str(Path(path).resolve())

    def get_or_create(self, path: str, kernel_name: str = "python3") -> KernelSession:
        """Return existing session or create a new one."""
        key = self._resolve_key(path)
        with self._lock:
            if key in self._sessions:
                session = self._sessions[key]
                if session.kernel_manager.is_alive():
                    session.touch()
                    return session
                # Dead kernel — clean up and recreate
                logger.warning("Kernel for %s found dead, recreating", path)
                self._cleanup_session(session)

            session = self._start_kernel(kernel_name)
            self._sessions[key] = session
            logger.info("Started kernel for %s (id=%s)", path, session.kernel_id)
            return session

    def restart(self, path: str, kernel_name: str = "python3") -> KernelSession:
        """Shutdown existing kernel and start a fresh one."""
        key = self._resolve_key(path)
        with self._lock:
            old = self._sessions.pop(key, None)
            if old:
                self._cleanup_session(old)
                logger.info("Shut down old kernel for %s", path)

            session = self._start_kernel(kernel_name)
            self._sessions[key] = session
            logger.info("Restarted kernel for %s (id=%s)", path, session.kernel_id)
            return session

    def shutdown(self, path: str) -> None:
        """Shutdown the kernel for a given notebook path."""
        key = self._resolve_key(path)
        with self._lock:
            session = self._sessions.pop(key, None)
            if session:
                self._cleanup_session(session)
                logger.info("Shut down kernel for %s", path)

    def shutdown_idle(self, max_idle_seconds: float = 1800) -> list[str]:
        """Shutdown sessions idle longer than *max_idle_seconds*. Returns shut-down paths."""
        now = datetime.now(timezone.utc)
        to_remove: list[str] = []
        with self._lock:
            for key, session in self._sessions.items():
                idle = (now - session.last_activity).total_seconds()
                if idle > max_idle_seconds:
                    to_remove.append(key)
            removed: list[str] = []
            for key in to_remove:
                session = self._sessions.pop(key)
                self._cleanup_session(session)
                removed.append(key)
                logger.info("Shut down idle kernel: %s (idle %.0fs)", key, (now - session.last_activity).total_seconds())
        return removed

    def list_sessions(self) -> dict[str, KernelSession]:
        """Return a snapshot of active sessions."""
        with self._lock:
            return dict(self._sessions)

    def shutdown_all(self) -> None:
        """Shutdown every active kernel. Used for graceful app shutdown."""
        with self._lock:
            for key, session in self._sessions.items():
                self._cleanup_session(session)
                logger.info("Shut down kernel: %s", key)
            self._sessions.clear()

    def _start_kernel(self, kernel_name: str) -> KernelSession:
        """Start a new kernel and return a KernelSession."""
        km = KernelManager(kernel_name=kernel_name)
        try:
            km.start_kernel()
            if not km.is_alive():
                raise KernelStartupError(f"Kernel '{kernel_name}' started but is not alive")
        except KernelStartupError:
            raise
        except Exception as exc:
            raise KernelStartupError(f"Failed to start kernel '{kernel_name}': {exc}") from exc

        kc = km.client()
        kc.start_channels()
        try:
            kc.wait_for_ready(timeout=_STARTUP_TIMEOUT)
        except Exception as exc:
            km.shutdown_kernel(now=True)
            raise KernelStartupError(f"Kernel not ready within {_STARTUP_TIMEOUT}s: {exc}") from exc

        return KernelSession(
            kernel_manager=km,
            kernel_client=kc,
            kernel_name=kernel_name,
        )

    @staticmethod
    def _cleanup_session(session: KernelSession) -> None:
        """Stop channels and shutdown kernel, swallowing errors."""
        try:
            session.kernel_client.stop_channels()  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            session.kernel_manager.shutdown_kernel(now=True)
        except Exception:
            pass
