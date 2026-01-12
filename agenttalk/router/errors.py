from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouterError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class RoutingNoTarget(RouterError):
    pass


class DagInvalid(RouterError):
    pass


class EnvelopeInvalid(RouterError):
    pass

