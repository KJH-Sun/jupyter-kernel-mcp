"""Custom error types for the notebook execution system."""


class NotebookError(Exception):
    """Base error for notebook operations."""


class NotebookNotFoundError(NotebookError):
    """Raised when a notebook file does not exist."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Notebook not found: {path}")


class CellIndexError(NotebookError):
    """Raised when a cell index is out of range."""

    def __init__(self, index: int, total: int) -> None:
        self.index = index
        self.total = total
        super().__init__(f"Cell index {index} out of range (notebook has {total} cells)")


class CellNotCodeError(NotebookError):
    """Raised when trying to execute a non-code cell."""

    def __init__(self, index: int, cell_type: str) -> None:
        self.index = index
        self.cell_type = cell_type
        super().__init__(f"Cell {index} is '{cell_type}', not 'code'. Cannot execute.")


class KernelError(NotebookError):
    """Raised on kernel-level failures."""


class KernelStartupError(KernelError):
    """Raised when kernel fails to start."""


class KernelExecutionTimeoutError(KernelError):
    """Raised when cell execution exceeds timeout."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        super().__init__(f"Cell execution timed out after {timeout}s")


class NotebookSaveError(NotebookError):
    """Raised when atomic save fails."""


class UnsafePath(NotebookError):
    """Raised when a notebook path attempts directory traversal."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Unsafe path rejected: {path}")
