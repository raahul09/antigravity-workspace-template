"""
Convenience entrypoint so `python agent.py` works from the repo root.

You can pass the task via CLI args or the AGENT_TASK env var.
Example:
    python agent.py --workspace /path/to/my-project "帮我写一个快速排序算法"
"""
import os
import sys
from pathlib import Path

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Antigravity Agent Engine")
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Path to the user workspace directory. "
        "Defaults to current working directory.",
    )
    parser.add_argument("task", nargs="*", help="Task to execute.")
    args = parser.parse_args()

    # Set WORKSPACE_PATH *before* importing Settings / GeminiAgent
    if args.workspace:
        os.environ["WORKSPACE_PATH"] = str(Path(args.workspace).resolve())

    from src.agent import GeminiAgent

    task = " ".join(args.task).strip() or os.environ.get(
        "AGENT_TASK", "帮助我查看今天的天气"
    )

    agent = GeminiAgent()
    try:
        agent.run(task)
    finally:
        agent.shutdown()


if __name__ == "__main__":
    main()
