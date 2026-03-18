"""
Antigravity CLI – ag init <target_dir>

Copies the Artifact-First cognitive architecture templates into any
project directory, making any AI IDE an industry-savvy architect.
"""

from __future__ import annotations

import shutil
import sys
import time
from importlib import resources as importlib_resources
from pathlib import Path

import typer
from rich.console import Console

from ag_cli.reader import append_to_memory, append_decision
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

# Use a group (rich_markup_mode) so subcommands like `ag init` are not
# flattened into the root command by Typer's single-command optimisation.
app = typer.Typer(
    name="ag",
    help="Antigravity – inject AI cognitive architecture into any project.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


# ── Helpers ─────────────────────────────────────────────────────────


def _get_templates_dir() -> Path:
    """Return the absolute path to the bundled templates/ directory.

    Works both in editable installs and built wheels because hatch
    force-includes the directory into the package.
    """
    pkg_root = importlib_resources.files("ag_cli")
    templates = pkg_root / "templates"
    # importlib.resources may return a Traversable; resolve to a real Path.
    return Path(str(templates))


def _copy_tree(src: Path, dst: Path) -> list[str]:
    """Recursively copy *src* into *dst*, preserving dotfiles.

    Returns a list of relative paths that were created.
    """
    created: list[str] = []
    for item in sorted(src.rglob("*")):
        if item.name == "__pycache__":
            continue
        relative = item.relative_to(src)
        target = dst / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(item, target)
            created.append(str(relative))
    return created


_REPO_ROOT = Path(__file__).resolve().parents[3]  # cli/src/ag_cli/cli.py → repo root


def _run_hub(workspace: Path, *args: str) -> int:
    """Console script first, then python -m fallback."""
    import subprocess

    ag_hub = shutil.which("ag-hub")
    if ag_hub:
        cmd = [ag_hub] + list(args) + ["--workspace", str(workspace)]
        return subprocess.run(cmd, check=False).returncode

    engine_dir = _REPO_ROOT / "engine"
    if (engine_dir / "antigravity_engine" / "hub" / "__main__.py").exists():
        cmd = [sys.executable, "-m", "antigravity_engine.hub"] + list(args) + ["--workspace", str(workspace)]
        return subprocess.run(cmd, cwd=str(engine_dir), check=False).returncode

    console.print("[red]Engine not installed. Install: pip install git+...#subdirectory=engine[/red]")
    return 1


def _run_engine(workspace: Path, *args: str) -> int:
    """Console script first, then python -m fallback."""
    import subprocess

    ag_engine = shutil.which("ag-engine")
    if ag_engine:
        cmd = [ag_engine] + list(args) + ["--workspace", str(workspace)]
        return subprocess.run(cmd, check=False).returncode

    engine_dir = _REPO_ROOT / "engine"
    if (engine_dir / "antigravity_engine" / "__main__.py").exists():
        cmd = [sys.executable, "-m", "antigravity_engine"] + list(args) + ["--workspace", str(workspace)]
        return subprocess.run(cmd, cwd=str(engine_dir), check=False).returncode

    console.print("[red]Engine not installed.[/red]")
    return 1


# ── Commands ────────────────────────────────────────────────────────


@app.command("init")
def init_cmd(
    target_dir: str = typer.Argument(
        ...,
        help="Directory to inject the cognitive architecture into.",
    ),
) -> None:
    """Inject the Artifact-First cognitive architecture into TARGET_DIR."""

    target = Path(target_dir).resolve()

    # ── Pre-flight checks ───────────────────────────────────────────
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
        console.print(f"[dim]Created directory [bold]{target}[/bold][/dim]")

    templates = _get_templates_dir()
    if not templates.exists():
        console.print(
            "[bold red]✗[/bold red] Templates directory not found. "
            "Is the package installed correctly?",
        )
        raise typer.Exit(code=1)

    # ── Copy templates with spinner ─────────────────────────────────
    with console.status(
        "[cyan]⚛  Injecting Artifact-First cognitive architecture…[/cyan]",
        spinner="dots",
    ):
        created = _copy_tree(templates, target)
        # let the user enjoy the spinner for a beat
        time.sleep(0.6)

    # ── Create artifacts scaffold ───────────────────────────────────
    with console.status(
        "[magenta]📂  Scaffolding artifacts directory…[/magenta]",
        spinner="dots",
    ):
        (target / "artifacts" / "logs").mkdir(parents=True, exist_ok=True)
        (target / "artifacts" / ".gitkeep").touch()
        (target / "artifacts" / "logs" / ".gitkeep").touch()
        time.sleep(0.3)

    # ── Success panel ───────────────────────────────────────────────
    tree = Tree(f"[bold green]{target.name}/[/bold green]")
    for path_str in created:
        tree.add(f"[dim]{path_str}[/dim]")
    artifacts_node = tree.add("[bold green]artifacts/[/bold green]")
    artifacts_node.add("[dim]logs/[/dim]")

    console.print()
    console.print(tree)
    console.print()

    next_steps = Text.assemble(
        ("Next steps:\n\n", "bold"),
        ("  1. ", "bold cyan"),
        ("cd ", ""),
        (str(target), "bold"),
        ("\n", ""),
        ("  2. ", "bold cyan"),
        ("Open the directory in your AI IDE (Cursor, VS Code, Windsurf…)\n", ""),
        ("  3. ", "bold cyan"),
        ("Start prompting — the cognitive architecture is already loaded.\n", ""),
    )

    console.print(
        Panel(
            next_steps,
            title="[bold green]✔ Antigravity initialized[/bold green]",
            border_style="green",
            padding=(1, 2),
        ),
    )


# ── Version ──────────────────────────────────────────────────────────


@app.command("version")
def version_cmd() -> None:
    """Print the CLI version."""
    from ag_cli import __version__

    console.print(f"[bold cyan]ag[/bold cyan] v{__version__}")


# ── Start Engine ─────────────────────────────────────────────────────


@app.command("start-engine")
def start_engine_cmd(
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        help="Path to the user workspace directory.",
    ),
    task: str = typer.Argument(
        "",
        help="Optional task to execute. If empty, uses AGENT_TASK env var.",
    ),
) -> None:
    """Launch the Antigravity Agent Engine targeting a workspace."""
    workspace_path = Path(workspace).resolve()

    if not workspace_path.exists():
        console.print(
            f"[bold red]✗[/bold red] Workspace not found: {workspace_path}"
        )
        raise typer.Exit(code=1)

    console.print(
        f"[cyan]⚛  Starting engine for workspace:[/cyan] "
        f"[bold]{workspace_path}[/bold]"
    )

    args: list[str] = []
    if task:
        args.append(task)

    code = _run_engine(workspace_path, *args)
    raise typer.Exit(code=code)


# ── Hub Commands ─────────────────────────────────────────────────────


@app.command("ask")
def ask_cmd(
    question: str = typer.Argument(..., help="Question about the project."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Project directory."),
) -> None:
    """Ask a question about the project (requires LLM)."""
    workspace_path = Path(workspace).resolve()
    code = _run_hub(workspace_path, "ask", question)
    raise typer.Exit(code=code)


@app.command("refresh")
def refresh_cmd(
    workspace: str = typer.Option(".", "--workspace", "-w", help="Project directory."),
    quick: bool = typer.Option(False, "--quick", help="Only scan changed files."),
) -> None:
    """Refresh project context in .antigravity/ (requires LLM)."""
    workspace_path = Path(workspace).resolve()
    args: list[str] = ["refresh"]
    if quick:
        args.append("--quick")
    code = _run_hub(workspace_path, *args)
    raise typer.Exit(code=code)


@app.command("report")
def report_cmd(
    message: str = typer.Argument(..., help="Report message to log."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Project directory."),
) -> None:
    """Log a report to .antigravity/memory/reports.md (no LLM needed)."""
    workspace_path = Path(workspace).resolve()
    target = append_to_memory(workspace_path, "reports.md", message)
    console.print(f"[green]Logged report to {target.relative_to(workspace_path)}[/green]")


@app.command("log-decision")
def log_decision_cmd(
    decision: str = typer.Argument(..., help="The decision made."),
    rationale: str = typer.Argument(..., help="Why this decision was made."),
    workspace: str = typer.Option(".", "--workspace", "-w", help="Project directory."),
) -> None:
    """Log an architectural decision to .antigravity/decisions/log.md (no LLM needed)."""
    workspace_path = Path(workspace).resolve()
    target = append_decision(workspace_path, decision, rationale)
    console.print(f"[green]Logged decision to {target.relative_to(workspace_path)}[/green]")


if __name__ == "__main__":
    app()
