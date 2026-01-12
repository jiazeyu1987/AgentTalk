from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeartbeatError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class SchemaInvalid(HeartbeatError):
    pass


class EnvelopeParseError(HeartbeatError):
    pass


class UnsafePath(HeartbeatError):
    pass

