from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from .errors import ErrorCode, PackagingSkillError
from .paths import AssetType, StoragePathResolver, storage_key_from_private_uri


DELIVERY_ASSET_TYPES = {
    AssetType.SUBTITLE_SRT,
    AssetType.SUBTITLE_VTT,
    AssetType.TARGET_MIX_AUDIO,
    AssetType.PREVIEW_VIDEO,
}
INTERMEDIATE_ASSET_TYPES = {
    AssetType.SOURCE_VIDEO,
    AssetType.SOURCE_AUDIO,
    AssetType.SOURCE_VOCAL,
    AssetType.BACKGROUND_AUDIO,
    AssetType.TTS_SEGMENT_AUDIO,
    AssetType.TARGET_VOCAL,
}


def create_package_zip(
    *,
    project_id: str,
    manifest: Mapping[str, Any],
    assets: list[dict[str, Any]],
    output_path: str | Path,
    resolver: StoragePathResolver,
    include_intermediate_assets: bool = True,
) -> list[str]:
    package_path = Path(output_path)
    package_path.parent.mkdir(parents=True, exist_ok=True)
    entries: list[str] = []
    written: set[str] = set()
    allowed_types = set(DELIVERY_ASSET_TYPES)
    if include_intermediate_assets:
        allowed_types.update(INTERMEDIATE_ASSET_TYPES)

    try:
        with ZipFile(package_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            entries.append("manifest.json")
            written.add("manifest.json")
            for asset in assets:
                asset_type = str(asset.get("type") or "")
                if asset_type == AssetType.PACKAGE_ZIP or asset_type not in allowed_types:
                    continue
                source_path = Path(resolver.input_path(asset))
                if not source_path.is_file():
                    raise PackagingSkillError(
                        ErrorCode.PACKAGE_FAILED,
                        f"Package input asset is missing: {source_path}",
                    )
                arcname = _archive_name(project_id, asset, source_path)
                if arcname in written:
                    continue
                archive.write(source_path, arcname)
                entries.append(arcname)
                written.add(arcname)
    except PackagingSkillError:
        raise
    except Exception as exc:  # pragma: no cover - zipfile boundary
        raise PackagingSkillError(ErrorCode.PACKAGE_FAILED, str(exc)) from exc
    return entries


def _archive_name(project_id: str, asset: Mapping[str, Any], local_path: Path) -> str:
    storage_key = str(asset.get("storage_key") or "")
    if not storage_key:
        uri = str(asset.get("uri") or "")
        if uri.startswith("storage://private/"):
            storage_key = storage_key_from_private_uri(uri)
    project_prefix = f"projects/{project_id}/"
    if storage_key.startswith(project_prefix):
        return storage_key[len(project_prefix) :]
    return local_path.name
