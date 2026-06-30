from __future__ import annotations


PRIVATE_URI_PREFIX = "storage://private/"


def tts_segment_path(project_id: str, language: str, segment_id: str) -> str:
    return f"projects/{project_id}/tts/{language}/{segment_id}.wav"


def private_uri(storage_key: str) -> str:
    return f"{PRIVATE_URI_PREFIX}{storage_key}"
