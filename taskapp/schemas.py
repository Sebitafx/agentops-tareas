from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskFilter = Literal["all", "pending", "completed"]


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)


class TaskPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    completed: bool | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> "TaskPatch":
        if not self.model_fields_set or any(
            getattr(self, name) is None for name in self.model_fields_set
        ):
            raise ValueError("Enviar al menos un campo; no se aceptan valores null")
        return self


class Task(BaseModel):
    id: UUID
    title: str
    description: str
    completed: bool
    created_at: datetime
    updated_at: datetime
