"""
Antigravity CLI – ag init <target_dir>

Copies the Artifact-First cognitive architecture templates into any
project directory, making any AI IDE an industry-savvy architect.
"""

from __future__ import annotations

import shutil
import time
from importlib import resources as importlib_resources
from pathlib import Path

import typer
from rich.console import Console
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
            shutil.copy2(item, target)
            created.append(str(relative))
    return created


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
    import subprocess
    import sys

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

    # Locate the engine entry point relative to this package.
    # In a monorepo install, engine/ is a sibling of cli/.
    engine_agent = Path(__file__).resolve().parent.parent.parent.parent.parent / "engine" / "agent.py"

    if not engine_agent.exists():
        console.print(
            f"[bold red]✗[/bold red] Engine not found at {engine_agent}\n"
            "[dim]Make sure the engine/ directory is present in the monorepo.[/dim]"
        )
        raise typer.Exit(code=1)

    cmd = [sys.executable, str(engine_agent), "--workspace", str(workspace_path)]
    if task:
        cmd.append(task)

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")

    try:
        result = subprocess.run(cmd, check=False)
        raise typer.Exit(code=result.returncode)
    except KeyboardInterrupt:
        console.print("\n[yellow]Engine stopped.[/yellow]")
        raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
