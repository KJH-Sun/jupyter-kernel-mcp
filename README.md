# Notebook Agent — Stateful Notebook Execution System

A local notebook execution system that lets AI agents run Jupyter notebook cells with persistent kernel state, output persistence, and structured JSON control surface.

## Quick Start

### Install

```bash
# GitHub에서 직접 설치
pip install git+https://github.com/<owner>/notebook-agent.git

# 또는 로컬 클론 후 설치
git clone https://github.com/<owner>/notebook-agent.git
cd notebook-agent
pip install -e ".[dev]"
```

### Claude Code MCP 서버로 사용

설치 후 프로젝트의 `.mcp.json`에 추가:

```json
{
  "mcpServers": {
    "notebook-runtime": {
      "command": "notebook-agent-mcp",
      "args": []
    }
  }
}
```

Claude Code를 (재)시작하면 다음 도구들이 자동으로 사용 가능해집니다:
- `open_notebook` — 노트북 열기 + 커널 시작
- `list_cells` — 셀 목록 조회
- `run_cell` — 단일 셀 실행
- `run_until` — 처음부터 N번 셀까지 실행
- `restart_kernel` — 커널 재시작
- `list_sessions` — 활성 세션 조회
- `shutdown_idle` — 유휴 커널 종료
- `save_notebook` — 노트북 저장

### Run the FastAPI Server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Use the CLI (no server required)

```bash
# Open a notebook (starts kernel)
notebook-agent open --path /path/to/notebook.ipynb

# List cells
notebook-agent list-cells --path /path/to/notebook.ipynb

# Run a single cell (0-based index)
notebook-agent run-cell --path /path/to/notebook.ipynb --cell 0

# Run all cells up to index 5 with fresh kernel
notebook-agent run-until --path /path/to/notebook.ipynb --cell 5 --mode restart_and_run_until

# Restart kernel
notebook-agent restart-kernel --path /path/to/notebook.ipynb

# List active sessions
notebook-agent sessions

# Shutdown idle kernels
notebook-agent shutdown-idle --max-idle 1800

# Save notebook
notebook-agent save --path /path/to/notebook.ipynb
```

All CLI commands output structured JSON.

## Execution Modes

### `reuse_existing_session` (default)

Reuses the existing kernel session. Variables, imports, and state from prior cell executions are preserved. Fast — only runs the requested cell.

Use when: running cells sequentially in order, or when prior cells have already been executed.

### `restart_and_run_until`

Shuts down the current kernel, starts a fresh one, then runs all code cells from cell 0 through the target cell. Guarantees clean, reproducible state.

Use when:
- A cell fails with `NameError` or `ImportError` (missing prior state)
- You want to ensure reproducible results
- The user asks to "run from scratch"

## Example Agent Workflow

```bash
# 1. Open notebook
notebook-agent open --path analysis.ipynb

# 2. Check cells
notebook-agent list-cells --path analysis.ipynb

# 3. Run cells in order
notebook-agent run-cell --path analysis.ipynb --cell 0
notebook-agent run-cell --path analysis.ipynb --cell 1

# 4. If cell 3 fails with NameError, retry with full state rebuild
notebook-agent run-cell --path analysis.ipynb --cell 3 --mode restart_and_run_until
```

## HTTP API

When the FastAPI server is running:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/notebooks/open` | POST | Open notebook, start kernel |
| `/notebooks/cells?path=...` | GET | List cells |
| `/notebooks/run-cell` | POST | Run a single cell |
| `/notebooks/run-until` | POST | Run cells 0..N |
| `/notebooks/restart-kernel` | POST | Restart kernel |
| `/notebooks/save` | POST | Save notebook |
| `/sessions` | GET | List active sessions |
| `/sessions/shutdown-idle` | POST | Shutdown idle kernels |

## Architecture

See [docs/architecture.md](docs/architecture.md) for detailed component design.

## Agent Usage Guide

See [docs/agent_skill.md](docs/agent_skill.md) for instructions on how an AI agent should use this system.

## Tests

```bash
pytest
```

Tests use real Jupyter kernels — requires `ipykernel` installed.
