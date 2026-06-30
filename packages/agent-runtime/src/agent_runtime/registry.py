from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import models


@dataclass(frozen=True)
class ResolvedSkillDefinition:
    skill_name: str
    skill_version: str
    enabled: bool
    default_provider: str | None
    input_schema: str
    output_schema: str
    timeout_seconds: int
    retry_limit: int


class SkillRegistry:
    def __init__(self, *, allow_missing_defaults: bool = False) -> None:
        self.allow_missing_defaults = allow_missing_defaults

    def resolve(
        self,
        db: Session,
        skill_name: str,
        skill_version: str | None = None,
    ) -> ResolvedSkillDefinition:
        statement = select(models.SkillDefinition).where(
            models.SkillDefinition.skill_name == skill_name,
            models.SkillDefinition.enabled.is_(True),
        )
        if skill_version is not None:
            statement = statement.where(models.SkillDefinition.skill_version == skill_version)
        definition = (
            db.execute(
                statement.order_by(
                    desc(models.SkillDefinition.created_at),
                    desc(models.SkillDefinition.skill_version),
                )
            )
            .scalars()
            .first()
        )
        if definition is None:
            if self.allow_missing_defaults:
                return ResolvedSkillDefinition(
                    skill_name=skill_name,
                    skill_version=skill_version or "1.0.0",
                    enabled=True,
                    default_provider=None,
                    input_schema=f"{_schema_prefix(skill_name)}Input",
                    output_schema=f"{_schema_prefix(skill_name)}Output",
                    timeout_seconds=120,
                    retry_limit=0,
                )
            raise LookupError(f"Enabled SkillDefinition not found for {skill_name}")
        return ResolvedSkillDefinition(
            skill_name=definition.skill_name,
            skill_version=definition.skill_version,
            enabled=definition.enabled,
            default_provider=definition.default_provider,
            input_schema=definition.input_schema,
            output_schema=definition.output_schema,
            timeout_seconds=definition.timeout_seconds,
            retry_limit=definition.retry_limit,
        )


def _schema_prefix(skill_name: str) -> str:
    return "".join(part.capitalize() for token in skill_name.split(".") for part in token.split("_"))
