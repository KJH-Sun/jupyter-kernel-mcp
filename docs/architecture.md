# Architecture

## Three-Layer Design

```
┌─────────────────────────────────────┐
│  Layer 3: Agent Skill Document      │  docs/agent_skill.md
│  (Rules for AI agent usage)         │
├─────────────────────────────────────┤
│  Layer 2: Agent Interface           │  cli/notebook_agent.py
│  (CLI with JSON output)             │  app/api/routes.py
│  (FastAPI HTTP endpoints)           │
├─────────────────────────────────────┤
│  Layer 1: Notebook Runtime          │  app/services/*
│  (Kernel management, execution,     │  app/infra/*
│   output persistence)               │  app/domain/*
└─────────────────────────────────────┘
```

## Layer 1: Runtime Components

### Domain (`app/domain/`)
- **models.py** — Pydantic models: ExecutionMode, CellInfo, ExecutionResult, SessionInfo, NotebookInfo
- **errors.py** — Typed exceptions: NotebookNotFoundError, CellIndexError, KernelError, etc.

### Infrastructure (`app/infra/`)
- **notebook_repository.py** — Loads/saves .ipynb via nbformat, validates paths, atomic write
- **atomic_writer.py** — tempfile + os.replace for crash-safe saves
- **file_lock.py** — Per-path threading.Lock registry for mutation serialization

### Services (`app/services/`)
- **kernel_session_registry.py** — Maps notebook path → live KernelManager/KernelClient. Handles create, reuse, restart, shutdown, idle cleanup.
- **cell_executor.py** — Sends execute requests to a kernel, collects IOPub messages until idle, handles timeout.
- **output_serializer.py** — Converts raw kernel messages to nbformat-compatible output dicts.
- **notebook_runtime_service.py** — Top-level orchestrator. Coordinates repo, registry, executor for all operations.

## Layer 2: Agent Interface

### CLI (`cli/notebook_agent.py`)
- Click-based CLI, directly imports service layer (no HTTP server needed)
- All output is structured JSON
- Commands: open, list-cells, run-cell, run-until, restart-kernel, sessions, shutdown-idle, save

### HTTP API (`app/api/`)
- FastAPI routes that delegate to NotebookRuntimeService
- Pydantic request/response schemas
- Domain errors mapped to HTTP status codes

## Execution Modes

### `reuse_existing_session`
- Default mode
- Uses existing kernel or creates one
- Preserves all prior execution state
- Fast — runs only the requested cell

### `restart_and_run_until`
- Shuts down existing kernel, starts fresh
- Runs all code cells from cell 0 through target
- Guarantees clean, reproducible state
- Slower but reliable when state is uncertain

## Data Flow: Run Cell

```
CLI/API request
  → NotebookRuntimeService.run_cell()
    → NotebookRepository.load()         # read .ipynb
    → KernelSessionRegistry.get_or_create()  # get/start kernel
    → CellExecutor.execute()             # send code, collect output
    → OutputSerializer.serialize_outputs()
    → NotebookRepository.update_cell_outputs()
    → NotebookRepository.save()          # atomic write
  ← ExecutionResult (JSON)
```

## Concurrency Model

- Single-process, multi-threaded
- Per-notebook-path threading.Lock for mutation serialization
- KernelSessionRegistry has its own internal lock for session management
- No distributed locking (single machine only)

## Path Safety

- `..` in path components is rejected
- Optional `NOTEBOOK_BASE_DIR` env var restricts access to a directory subtree
