from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    details: dict[str, Any] | None = None


class CommandHandler(Protocol):
    def handle_command(self, *, envelope: dict, command: dict, context: dict) -> CommandResult: ...


class DefaultCommandHandler:
    def handle_command(self, *, envelope: dict, command: dict, context: dict) -> CommandResult:
        return CommandResult(ok=True, details={"note": "default handler: no-op"})

