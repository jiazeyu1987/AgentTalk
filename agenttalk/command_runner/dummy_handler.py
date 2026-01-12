from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agenttalk.heartbeat.handlers import CommandResult


@dataclass(frozen=True)
class DummyArtifactHandler:
    def handle_command(self, *, envelope: dict, command: dict, context: dict) -> CommandResult:
        produces = command.get("produces") or []
        if not isinstance(produces, list) or not produces:
            return CommandResult(ok=False, details={"error": "command.produces is required for DummyArtifactHandler"})

        prompt = str(command.get("prompt") or "")
        artifacts: list[dict[str, Any]] = []
        for item in produces:
            if not isinstance(item, dict):
                continue
            output_name = item.get("output_name")
            files = item.get("files")
            if not isinstance(output_name, str) or not isinstance(files, list) or not files:
                continue
            produced_files: list[dict[str, Any]] = []
            for f in files:
                if not isinstance(f, dict):
                    continue
                path = f.get("path")
                if not isinstance(path, str):
                    continue
                content = (f"DUMMY OUTPUT\noutput_name={output_name}\nprompt={prompt}\n").encode("utf-8")
                produced_files.append({"path": path, "content": content, "content_type": f.get("content_type")})
            if produced_files:
                artifacts.append({"output_name": output_name, "files": produced_files})

        if not artifacts:
            return CommandResult(ok=False, details={"error": "no valid produces entries"})

        return CommandResult(ok=True, details={"artifacts": artifacts})


handler = DummyArtifactHandler()

