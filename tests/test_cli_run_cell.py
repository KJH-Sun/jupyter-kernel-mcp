"""Test the CLI interface for notebook execution."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from cli.notebook_agent import cli


def test_cli_open(sample_notebook: Path):
    """CLI open command should return notebook info."""
    runner = CliRunner()
    result = runner.invoke(cli, ["open", "--path", str(sample_notebook)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert data["notebook"]["cell_count"] == 3


def test_cli_list_cells(sample_notebook: Path):
    """CLI list-cells should return all cells."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list-cells", "--path", str(sample_notebook)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert len(data["cells"]) == 3


def test_cli_run_cell(sample_notebook: Path):
    """CLI run-cell should execute and return JSON result."""
    runner = CliRunner()

    # Open first
    runner.invoke(cli, ["open", "--path", str(sample_notebook)])

    # Run cell 0
    result = runner.invoke(cli, [
        "run-cell", "--path", str(sample_notebook), "--cell", "0",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert data["result"]["success"] is True

    # Run cell 1 (depends on cell 0)
    result = runner.invoke(cli, [
        "run-cell", "--path", str(sample_notebook), "--cell", "1",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert data["result"]["success"] is True


def test_cli_run_until(sample_notebook: Path):
    """CLI run-until should run all cells up to target."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        "run-until", "--path", str(sample_notebook), "--cell", "2",
        "--mode", "restart_and_run_until",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert len(data["results"]) == 3


def test_cli_sessions(sample_notebook: Path):
    """CLI sessions should show active sessions after open."""
    runner = CliRunner()
    runner.invoke(cli, ["open", "--path", str(sample_notebook)])
    result = runner.invoke(cli, ["sessions"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"
    assert len(data["sessions"]) >= 1


def test_cli_restart_kernel(sample_notebook: Path):
    """CLI restart-kernel should succeed."""
    runner = CliRunner()
    runner.invoke(cli, ["open", "--path", str(sample_notebook)])
    result = runner.invoke(cli, ["restart-kernel", "--path", str(sample_notebook)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "ok"


def test_cli_invalid_path():
    """CLI should return error JSON for non-existent notebook."""
    runner = CliRunner()
    result = runner.invoke(cli, ["open", "--path", "/nonexistent/notebook.ipynb"])
    assert result.exit_code != 0
    data = json.loads(result.output)
    assert data["status"] == "error"
