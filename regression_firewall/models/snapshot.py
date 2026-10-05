from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Optional

from .change import Change


@dataclass
class ProbeCapture:
    """Raw result of running one probe once.

    ``ok=False`` means the probe could not reach the subject at all
    (connection refused, timeout, import crash). An HTTP error status is a
    *successful* capture — it is behavior.
    """

    probe_id: str
    target: str
    ok: bool = True
    error: Optional[str] = None
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ProbeCapture":
        return cls(
            probe_id=d["probe_id"],
            target=d["target"],
            ok=d.get("ok", True),
            error=d.get("error"),
            data=d.get("data") or {},
        )


@dataclass
class Snapshot:
    """Captured behavior of the project at one point in time."""

    schema_version: str
    created_at: str
    tool_version: str
    config_hash: str
    project: dict = field(default_factory=dict)
    surfaces: dict = field(default_factory=dict)  # surface -> list[ProbeCapture]
    provenance: dict = field(default_factory=dict)  # git state, snapshot hash, rebaseline info

    def content_hash(self) -> str:
        from ..provenance import content_hash

        return content_hash(self.to_dict())

    def captures(self, surface: str) -> list:
        return self.surfaces.get(surface, [])

    def capture_map(self, surface: str) -> dict:
        return {c.probe_id: c for c in self.captures(surface)}

    def probe_count(self) -> int:
        return sum(len(v) for v in self.surfaces.values())

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "tool_version": self.tool_version,
            "config_hash": self.config_hash,
            "project": self.project,
            "surfaces": {
                name: [c.to_dict() for c in captures]
                for name, captures in self.surfaces.items()
            },
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Snapshot":
        version = str(d.get("schema_version", ""))
        if version != "1":
            raise ValueError(
                f"Unsupported snapshot schema_version {version!r} (expected '1'). "
                "Re-run 'regression-firewall baseline' with the current tool version."
            )
        return cls(
            schema_version="1",
            created_at=d.get("created_at", ""),
            tool_version=d.get("tool_version", ""),
            config_hash=d.get("config_hash", ""),
            project=d.get("project") or {},
            surfaces={
                name: [ProbeCapture.from_dict(c) for c in captures]
                for name, captures in (d.get("surfaces") or {}).items()
            },
            provenance=d.get("provenance") or {},
        )
