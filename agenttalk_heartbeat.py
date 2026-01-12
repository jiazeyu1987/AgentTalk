from __future__ import annotations

import argparse
from pathlib import Path

from agenttalk.heartbeat.app import run_forever


def main(argv: list[str] | None = None, *, runner=run_forever) -> None:
    p = argparse.ArgumentParser(description="AgentTalk heartbeat daemon (MVP)")
    p.add_argument("--agent-root", required=True, type=Path, help="Path to agents/<agent_id>/")
    p.add_argument(
        "--schemas-base-dir",
        default=Path("doc/rule/templates/schemas"),
        type=Path,
        help="Directory containing *.schema.json",
    )
    p.add_argument("--handler-module", default=None, help="Python module exposing `handler` object")
    p.add_argument("--config", default=None, type=Path, help="Path to heartbeat_config.json (default: agent root)")
    args = p.parse_args(argv)

    runner(
        agent_root=args.agent_root,
        schemas_base_dir=args.schemas_base_dir,
        handler_module=args.handler_module,
        config_path=args.config,
    )


if __name__ == "__main__":
    main()
