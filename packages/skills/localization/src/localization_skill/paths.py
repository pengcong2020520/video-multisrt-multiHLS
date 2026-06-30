from __future__ import annotations


PRIVATE_URI_PREFIX = "storage://private/"


def translation_json_path(project_id: str, language: str) -> str:
    return f"projects/{project_id}/translations/{language}.json"


def private_uri(storage_key: str) -> str:
    return f"{PRIVATE_URI_PREFIX}{storage_key}"
