from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from localization_skill.paths import private_uri


class JsonAssetWriter:
    def __init__(self, *, storage_root: str | Path | None = None) -> None:
        self.storage_root = Path(storage_root) if storage_root else None

    def write_json(self, storage_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.storage_root is not None:
            destination = self.storage_root / storage_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        return {
            "asset_id": _asset_id_from_key(storage_key),
            "uri": private_uri(storage_key),
            "storage_key": storage_key,
        }


def _asset_id_from_key(storage_key: str) -> str:
    safe = storage_key.replace("/", "_").replace(".", "_").replace("-", "_")
    return f"asset_{safe}"
