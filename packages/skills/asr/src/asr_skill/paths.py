from __future__ import annotations


PRIVATE_URI_PREFIX = "storage://private/"


def asr_source_segments_path(project_id: str) -> str:
    return f"projects/{project_id}/asr/source_segments.json"


def private_uri(storage_key: str) -> str:
    return f"{PRIVATE_URI_PREFIX}{storage_key}"
