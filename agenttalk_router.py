from __future__ import annotations

import argparse
from pathlib import Path

from agenttalk.router.app import run_forever


def main(argv: list[str] | None = None, *, runner=run_forever) -> None:
    p = argparse.ArgumentParser(description="AgentTalk router (MVP)")
    p.add_argument("--agents-root", required=True, type=Path, help="Path to agents/ root")
    p.add_argument("--system-runtime", required=True, type=Path, help="Path to system_runtime/ root")
    p.add_argument(
        "--schemas-base-dir",
        default=Path("doc/rule/templates/schemas"),
        type=Path,
        help="Directory containing *.schema.json",
    )
    args = p.parse_args(argv)
    runner(agents_root=args.agents_root, system_runtime=args.system_runtime, schemas_base_dir=args.schemas_base_dir)


if __name__ == "__main__":
    main()

