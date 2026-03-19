"""Tests for ag init --force flag."""
from pathlib import Path

from typer.testing import CliRunner

from ag_cli.cli import app

runner = CliRunner()


def test_init_skips_existing_without_force(tmp_path: Path) -> None:
    """Without --force, existing files are not overwritten."""
    # First init
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0

    # Write a marker into an existing file to check it stays intact
    ag_dir = tmp_path / ".antigravity"
    if ag_dir.exists():
        md_files = list(ag_dir.glob("*.md"))
        if md_files:
            target = md_files[0]
            target.write_text("CUSTOM CONTENT", encoding="utf-8")

            # Second init without --force
            result = runner.invoke(app, ["init", str(tmp_path)])
            assert result.exit_code == 0

            # Custom content should be preserved
            assert target.read_text(encoding="utf-8") == "CUSTOM CONTENT"


def test_init_overwrites_with_force(tmp_path: Path) -> None:
    """With --force, existing files are overwritten."""
    # First init
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0

    # Write a marker into an existing file
    ag_dir = tmp_path / ".antigravity"
    if ag_dir.exists():
        md_files = list(ag_dir.glob("*.md"))
        if md_files:
            target = md_files[0]
            original = target.read_text(encoding="utf-8")
            target.write_text("CUSTOM CONTENT", encoding="utf-8")

            # Second init with --force
            result = runner.invoke(app, ["init", "--force", str(tmp_path)])
            assert result.exit_code == 0

            # File should be restored to original template content
            assert target.read_text(encoding="utf-8") == original
