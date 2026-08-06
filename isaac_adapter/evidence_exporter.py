from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EvidenceExporter:
    def __init__(self, evidence_root: Path):
        self.evidence_root = evidence_root

    def save_summary(self, storage_key: str, summary: dict[str, Any]) -> Path:
        target = (self.evidence_root / storage_key).resolve()
        root = self.evidence_root.resolve()
        if root not in target.parents:
            raise ValueError("storage_key must remain under evidence_root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
