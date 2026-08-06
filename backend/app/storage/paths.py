from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core.config import get_settings


@dataclass(frozen=True)
class StoragePaths:
    root: Path
    database: Path
    evidence: Path
    isaac: Path
    logs: Path
    backups: Path

    @classmethod
    def from_settings(cls) -> "StoragePaths":
        root = get_settings().sitegit_data_root
        return cls(
            root=root,
            database=root / "database",
            evidence=root / "evidence",
            isaac=root / "isaac",
            logs=root / "logs",
            backups=root / "backups",
        )

    def resolve_storage_key(self, storage_key: str) -> Path:
        """상대 storage_key를 Evidence 루트 아래 실제 경로로 해석합니다."""
        candidate = (self.evidence / storage_key).resolve()
        evidence_root = self.evidence.resolve()
        if evidence_root not in candidate.parents and candidate != evidence_root:
            raise ValueError("storage_key must remain inside the evidence directory")
        return candidate
