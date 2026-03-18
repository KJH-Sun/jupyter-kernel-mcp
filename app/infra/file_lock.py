"""Simple per-path threading lock registry.

Provides mutual exclusion for concurrent operations on the same notebook
within a single process.
"""

from __future__ import annotations

import threading
from pathlib import Path


class FileLockRegistry:
    """Maps resolved file paths to threading locks."""

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def get(self, path: str | Path) -> threading.Lock:
        """Return the lock for *path*, creating it if needed."""
        key = str(Path(path).resolve())
        with self._registry_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def remove(self, path: str | Path) -> None:
        """Remove the lock entry (e.g. after notebook close)."""
        key = str(Path(path).resolve())
        with self._registry_lock:
            self._locks.pop(key, None)
