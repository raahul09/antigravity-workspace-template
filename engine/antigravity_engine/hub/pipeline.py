"""Hub pipelines — refresh and ask."""
from __future__ import annotations

import subprocess
from pathlib import Path


async def refresh_pipeline(workspace: Path, quick: bool = False) -> None:
    """Scan project and update .antigravity/conventions.md.

    Args:
        workspace: Project root directory.
        quick: If True, only scan files changed since last refresh.
    """
    from antigravity_engine.config import Settings
    from antigravity_engine.hub.agents import build_refresh_agent, create_model
    from antigravity_engine.hub.scanner import full_scan, quick_scan

    settings = Settings()
    model = create_model(settings)

    sha_file = workspace / ".antigravity" / ".last_refresh_sha"

    if quick and sha_file.exists():
        since_sha = sha_file.read_text(encoding="utf-8").strip()
        report = quick_scan(workspace, since_sha)
    else:
        report = full_scan(workspace)

    # Build prompt from scan report
    prompt = _format_scan_report(report)

    agent = build_refresh_agent(model)
    from agents import Runner

    result = await Runner.run(agent, prompt)
    conventions_content = result.final_output

    # Write conventions
    ag_dir = workspace / ".antigravity"
    ag_dir.mkdir(parents=True, exist_ok=True)
    (ag_dir / "conventions.md").write_text(conventions_content, encoding="utf-8")

    # Save SHA checkpoint
    current_sha = _get_head_sha(workspace)
    if current_sha:
        sha_file.write_text(current_sha, encoding="utf-8")

    print(f"Updated {ag_dir / 'conventions.md'}")


async def ask_pipeline(workspace: Path, question: str) -> str:
    """Answer a question about the project.

    Args:
        workspace: Project root directory.
        question: Natural language question.

    Returns:
        Answer string.
    """
    from antigravity_engine.config import Settings
    from antigravity_engine.hub.agents import build_reviewer_agent, create_model

    settings = Settings()
    model = create_model(settings)

    # Gather context
    context_parts: list[str] = []

    conventions = workspace / ".antigravity" / "conventions.md"
    if conventions.exists():
        context_parts.append(conventions.read_text(encoding="utf-8"))

    rules = workspace / ".antigravity" / "rules.md"
    if rules.exists():
        context_parts.append(rules.read_text(encoding="utf-8"))

    decisions = workspace / ".antigravity" / "decisions" / "log.md"
    if decisions.exists():
        context_parts.append(decisions.read_text(encoding="utf-8"))

    context = "\n---\n".join(context_parts) if context_parts else "(no context available)"
    prompt = f"Project context:\n{context}\n\nQuestion: {question}"

    agent = build_reviewer_agent(model)
    from agents import Runner

    result = await Runner.run(agent, prompt)
    return result.final_output


def _format_scan_report(report) -> str:
    """Format a ScanReport into a prompt string."""
    lines = [f"Project root: {report.root}"]

    if report.languages:
        lines.append("\nLanguages (file count):")
        for lang, count in list(report.languages.items())[:10]:
            lines.append(f"  - {lang}: {count}")

    if report.frameworks:
        lines.append("\nFrameworks/Tools detected:")
        for fw in report.frameworks:
            lines.append(f"  - {fw}")

    if report.top_dirs:
        lines.append(f"\nTop-level directories: {', '.join(report.top_dirs)}")

    lines.append(f"\nTotal files: {report.file_count}")
    lines.append(f"Has tests: {report.has_tests}")
    lines.append(f"Has CI: {report.has_ci}")
    lines.append(f"Has Docker: {report.has_docker}")

    if report.readme_snippet:
        lines.append(f"\nREADME excerpt:\n{report.readme_snippet}")

    return "\n".join(lines)


def _get_head_sha(workspace: Path) -> str | None:
    """Get the current HEAD commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(workspace),
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None
