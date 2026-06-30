from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./api.sqlite3"
    public_url_base: str = "http://localhost:8000/object"
    storage_secret: str = "dev-storage-secret"
    signed_url_ttl_seconds: int = 3600
    auth_required: bool = True
    redis_url: str | None = None
    create_schema: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("API_DATABASE_URL", cls.database_url),
            public_url_base=os.getenv("API_PUBLIC_URL_BASE", cls.public_url_base),
            storage_secret=os.getenv("API_STORAGE_SECRET", cls.storage_secret),
            signed_url_ttl_seconds=int(
                os.getenv("API_SIGNED_URL_TTL_SECONDS", str(cls.signed_url_ttl_seconds))
            ),
            auth_required=os.getenv("API_AUTH_REQUIRED", "true").lower()
            not in {"0", "false", "no"},
            redis_url=os.getenv("REDIS_URL"),
            create_schema=os.getenv("API_CREATE_SCHEMA", "true").lower()
            not in {"0", "false", "no"},
        )
