from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProducedFile:
    path: str
    content: bytes
    content_type: str | None = None


@dataclass(frozen=True)
class ProducedArtifact:
    output_name: str
    files: list[ProducedFile]
    subtype: str | None = None
    notes: str | None = None


def artifacts_from_details(details: dict[str, Any] | None) -> list[ProducedArtifact]:
    if not details:
        return []
    raw = details.get("artifacts")
    if not isinstance(raw, list):
        return []
    artifacts: list[ProducedArtifact] = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        output_name = a.get("output_name")
        files = a.get("files")
        if not isinstance(output_name, str) or not isinstance(files, list):
            continue
        produced_files: list[ProducedFile] = []
        for f in files:
            if not isinstance(f, dict):
                continue
            path = f.get("path")
            content = f.get("content")
            if not isinstance(path, str) or not isinstance(content, (bytes, bytearray)):
                continue
            produced_files.append(
                ProducedFile(
                    path=path,
                    content=bytes(content),
                    content_type=f.get("content_type") if isinstance(f.get("content_type"), str) else None,
                )
            )
        if produced_files:
            artifacts.append(
                ProducedArtifact(
                    output_name=output_name,
                    files=produced_files,
                    subtype=a.get("subtype") if isinstance(a.get("subtype"), str) else None,
                    notes=a.get("notes") if isinstance(a.get("notes"), str) else None,
                )
            )
    return artifacts

