from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from agenttalk.dashboard.app import create_app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="AgentTalk dashboard API (MVP)")
    p.add_argument("--system-runtime", required=True, type=Path, help="Path to system_runtime/")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", default=8000, type=int)
    args = p.parse_args(argv)

    app = create_app(system_runtime=args.system_runtime)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

