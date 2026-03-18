# Notebook Execution Agent Skill

Instructions for an AI agent to control the stateful notebook execution system.

## System Overview

You have access to a notebook execution runtime that manages real Jupyter kernels.
You can run cells, inspect state, restart kernels, and persist outputs — all through
structured CLI commands or HTTP API calls.

**Every command returns JSON.** Parse it to determine success/failure and extract outputs.

---

## CLI Commands

All commands are invoked via `python cli/notebook_agent.py <command> [options]`.

| Command | Description |
|---------|-------------|
| `open --path <path>` | Open notebook, start kernel session |
| `list-cells --path <path>` | List all cells with index, type, source preview |
| `run-cell --path <path> --cell <n> [--mode ...] [--timeout N]` | Run a single cell |
| `run-until --path <path> --cell <n> [--mode ...] [--timeout N]` | Run all code cells 0..n |
| `restart-kernel --path <path>` | Restart the kernel (clears all state) |
| `sessions` | List all active kernel sessions |
| `shutdown-idle [--max-idle N]` | Shutdown kernels idle > N seconds |
| `get-cell-output --path <path> --cell <n>` | Read cell outputs and extract images |
| `save --path <path>` | Force-save the notebook file |

---

## Rules for Interpreting User Requests

### Rule 1: Cell Numbering

Users speak in **1-based** numbering. The system uses **0-based** indexing.

- "Run cell 2" → `--cell 1`
- "Run cell 1" → `--cell 0`
- "Run the first cell" → `--cell 0`

Always subtract 1 from the user's number before passing to the CLI.

### Rule 2: Default Execution Mode

Always default to `reuse_existing_session` for `run-cell`.

```bash
python cli/notebook_agent.py run-cell --path notebook.ipynb --cell 1 --mode reuse_existing_session
```

This preserves kernel state from prior executions. Only use `restart_and_run_until`
when explicitly needed (see Rule 3).

### Rule 3: When to Use `restart_and_run_until`

Use this mode when:
1. A cell fails with `NameError`, `ImportError`, or other missing-state errors.
2. The user explicitly asks to "run from scratch" or "re-run everything".
3. You suspect the kernel state is corrupted or inconsistent.

```bash
python cli/notebook_agent.py run-cell --path notebook.ipynb --cell 5 --mode restart_and_run_until
```

This will:
1. Restart the kernel (fresh state)
2. Run all code cells from cell 0 through cell 5
3. Return the result of cell 5

### Rule 4: Markdown Cells

If the target cell is a markdown cell, **do not attempt to execute it**.
Inform the user:

> "Cell 3 is a markdown cell and cannot be executed. Did you mean cell 4?"

Check cell types first with `list-cells` if unsure.

### Rule 5: Resolving Notebook Context

If the user says "this notebook" or "the current notebook":
- Use the notebook path from the most recent `open` command in the conversation.
- If no notebook has been opened, ask the user for the path.

Always use absolute paths when possible.

### Rule 6: Open Before Execute

Before running cells, ensure the notebook has been opened:
```bash
python cli/notebook_agent.py open --path /path/to/notebook.ipynb
```

This loads the notebook and ensures a kernel is running.

### Rule 7: Summarizing Results

After execution, report to the user:

1. **Cell number** (1-based, as the user thinks of it)
2. **Success or failure**
3. **Key outputs** — text output, return values, or error messages
4. **Whether the notebook was updated** (always yes on successful execution)

Example summary:
> Cell 3 executed successfully.
> Output: `42`
> The notebook file has been updated with the execution results.

For errors:
> Cell 3 failed with NameError: name 'df' is not defined.
> This likely means a prior cell was not executed. Retrying with restart_and_run_until...

### Rule 8: Error Recovery Flow

When a cell fails:
1. Check if the error is a missing-state error (NameError, ImportError, AttributeError)
2. If yes, retry with `restart_and_run_until`
3. If the retry also fails, report the error to the user with the traceback
4. Do NOT retry more than once automatically

### Rule 9: Long-Running Cells

If a cell might take a long time (data loading, training, etc.):
- Use `--timeout` to extend the default (120s): `--timeout 600`
- Inform the user that execution is in progress

### Rule 10: Viewing Image Outputs

Cell outputs may contain images (matplotlib charts, seaborn plots, etc.) stored as base64.
To inspect them:

1. Call `get-cell-output --path <path> --cell <n>` to extract images.
2. The response includes `image_paths` — a list of saved PNG/JPEG file paths.
3. Use the `Read` tool to open each image path and view it visually.

```bash
python cli/notebook_agent.py get-cell-output --path notebook.ipynb --cell 3
# → {"image_paths": ["/tmp/notebook-agent/notebook/cell_3_0.png"]}
# Then use Read to view the image file
```

### Rule 11: Multiple Cell Execution

If the user says "run cells 3 through 7":
```bash
python cli/notebook_agent.py run-until --path notebook.ipynb --cell 6 --mode reuse_existing_session
```

Note: `--cell 6` because user says "7" (1-based) → 6 (0-based), and `run-until` is inclusive.

---

## HTTP API Alternative

If the FastAPI server is running (`uvicorn app.main:app --port 8000`), you can use HTTP:

| Endpoint | Method | Body |
|----------|--------|------|
| `/notebooks/open` | POST | `{"path": "..."}` |
| `/notebooks/cells?path=...` | GET | — |
| `/notebooks/run-cell` | POST | `{"path": "...", "cell_index": N, "mode": "..."}` |
| `/notebooks/run-until` | POST | `{"path": "...", "cell_index": N, "mode": "..."}` |
| `/notebooks/restart-kernel` | POST | `{"path": "..."}` |
| `/sessions` | GET | — |
| `/sessions/shutdown-idle` | POST | `{"max_idle_seconds": N}` |

---

## Workflow Examples

### Basic: Run a specific cell
```
1. open --path /project/analysis.ipynb
2. list-cells --path /project/analysis.ipynb     # verify cell types
3. run-cell --path /project/analysis.ipynb --cell 2
4. Parse JSON output, report to user
```

### Recovery: Handle missing state
```
1. run-cell --path notebook.ipynb --cell 5
2. Result: NameError — 'df' is not defined
3. run-cell --path notebook.ipynb --cell 5 --mode restart_and_run_until
4. All cells 0-5 run in fresh kernel
5. Report final result
```

### Full run: Execute entire notebook
```
1. open --path notebook.ipynb
2. list-cells --path notebook.ipynb              # find last cell index
3. run-until --path notebook.ipynb --cell <last_index> --mode restart_and_run_until
4. Report results for each cell
```
