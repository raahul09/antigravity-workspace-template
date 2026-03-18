"""Bootstrap. Sets env vars BEFORE importing config-dependent modules."""
import argparse
import os
import sys
from pathlib import Path


def engine_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-engine")
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("task", nargs="*")
    args = parser.parse_args()

    if args.workspace:
        os.environ["WORKSPACE_PATH"] = str(Path(args.workspace).resolve())

    try:
        from antigravity_engine.agent import GeminiAgent  # lazy import

        task = " ".join(args.task).strip() or os.environ.get("AGENT_TASK", "")
        agent = GeminiAgent()
        try:
            agent.run(task)
        finally:
            agent.shutdown()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def hub_main() -> None:
    parser = argparse.ArgumentParser(prog="ag-hub")
    sub = parser.add_subparsers(dest="cmd")

    p_ask = sub.add_parser("ask")
    p_ask.add_argument("question")
    p_ask.add_argument("--workspace", default=".")

    p_refresh = sub.add_parser("refresh")
    p_refresh.add_argument("--workspace", default=".")
    p_refresh.add_argument("--quick", action="store_true")

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        sys.exit(1)

    os.environ["WORKSPACE_PATH"] = str(Path(args.workspace).resolve())

    try:
        if args.cmd == "ask":
            import asyncio
            from antigravity_engine.hub.pipeline import ask_pipeline

            print(asyncio.run(ask_pipeline(Path(args.workspace).resolve(), args.question)))
        elif args.cmd == "refresh":
            import asyncio
            from antigravity_engine.hub.pipeline import refresh_pipeline

            asyncio.run(refresh_pipeline(Path(args.workspace).resolve(), args.quick))
        else:
            parser.print_help()
            sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
