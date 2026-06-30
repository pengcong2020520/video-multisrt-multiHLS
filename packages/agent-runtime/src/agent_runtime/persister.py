"""Persistence boundary for skill responses.

The agent-runtime package orchestrates skill execution but must not depend on
the concrete SQLAlchemy models defined in ``app.models``.  Instead it defines a
``ResponsePersisterPort`` protocol and a ``SkillResponsePersister`` helper that
delegates to an injected backend.

Apps that embed the runtime (e.g. ``apps/api``) provide a concrete
implementation of ``ResponsePersisterPort`` and inject it into the runtime via
``AgentRuntime(skill_runner=..., persister=...)``.
"""

from __future__ import annotations

from typing import Any, Protocol

from agent_runtime.contracts import SkillResponse


class ResponsePersisterPort(Protocol):
    """Persist a skill response's outputs/assets to the application database.

    Implementations are provided by the host application (apps/api) and receive
    a SQLAlchemy ``Session`` plus the response metadata.  The runtime calls
    ``persist`` after every successful skill invocation.
    """

    def persist(
        self,
        db: Any,
        *,
        project_id: str,
        run_id: str,
        skill_name: str,
        target_language: str | None,
        response: SkillResponse,
    ) -> None:
        ...


class NoopResponsePersister:
    """Default persister that performs no persistence.

    Used when no concrete persister is injected, preserving backward
    compatibility with code paths that only care about skill invocation.
    """

    def persist(
        self,
        db: Any,
        *,
        project_id: str,
        run_id: str,
        skill_name: str,
        target_language: str | None,
        response: SkillResponse,
    ) -> None:
        return None


__all__ = ["NoopResponsePersister", "ResponsePersisterPort"]
