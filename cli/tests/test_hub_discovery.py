"""Tests for _run_hub() and _run_engine() discovery logic."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_run_hub_console_script_found() -> None:
    """When ag-hub is on PATH, uses it directly."""
    from ag_cli.cli import _run_hub

    with patch("shutil.which", return_value="/usr/local/bin/ag-hub"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            code = _run_hub(Path("/tmp/project"), "ask", "What?")

    assert code == 0
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "/usr/local/bin/ag-hub"
    assert "ask" in cmd
    assert "What?" in cmd
    assert "--workspace" in cmd


def test_run_hub_fallback_to_python_m(tmp_path: Path) -> None:
    """When no console script but monorepo dir exists, falls back to python -m."""
    from ag_cli.cli import _run_hub, _REPO_ROOT

    # Create the marker file at the expected location
    hub_main = _REPO_ROOT / "engine" / "antigravity_engine" / "hub" / "__main__.py"
    # This file actually exists in our repo, so this should work
    if hub_main.exists():
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                code = _run_hub(Path("/tmp/project"), "refresh")

        assert code == 0
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd
        assert "antigravity_engine.hub" in cmd


def test_run_engine_console_script_found() -> None:
    """When ag-engine is on PATH, uses it directly."""
    from ag_cli.cli import _run_engine

    with patch("shutil.which", return_value="/usr/local/bin/ag-engine"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=42)
            code = _run_engine(Path("/tmp/project"), "some-task")

    assert code == 42
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "/usr/local/bin/ag-engine"


def test_run_engine_fallback_to_python_m() -> None:
    """When no console script but monorepo dir exists, falls back."""
    from ag_cli.cli import _run_engine, _REPO_ROOT

    main_py = _REPO_ROOT / "engine" / "antigravity_engine" / "__main__.py"
    if main_py.exists():
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                code = _run_engine(Path("/tmp/project"))

        assert code == 0
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd
        assert "antigravity_engine" in cmd


def test_run_hub_neither_found(tmp_path: Path) -> None:
    """Returns 1 when neither console script nor monorepo dir found."""
    from ag_cli.cli import _run_hub

    with patch("shutil.which", return_value=None):
        with patch("ag_cli.cli._REPO_ROOT", tmp_path):
            code = _run_hub(Path("/tmp/project"), "ask", "test")

    assert code == 1


def test_run_engine_exit_code_propagation() -> None:
    """Exit code from subprocess is propagated."""
    from ag_cli.cli import _run_engine

    with patch("shutil.which", return_value="/usr/local/bin/ag-engine"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=7)
            code = _run_engine(Path("/tmp/project"))

    assert code == 7
