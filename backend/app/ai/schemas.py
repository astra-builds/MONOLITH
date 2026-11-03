"""Validated contracts shared by AI planning, previews, and execution.

These models deliberately describe intent and proposals rather than database
rows. They allow the backend to reject unsafe or incomplete model output
before it reaches the scheduler or persistence layer.
"""

from datetime import date, time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskIntent(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    estimated_minutes: int = Field(default=60, ge=1, le=24 * 60)
    estimate_source: Literal["user", "ai", "profile", "unknown"] = "unknown"
    estimate_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    deadline: Optional[date] = None
    priority: int = Field(default=3, ge=1, le=5)
    preferred_days: list[int] = Field(default_factory=list)
    preferred_start: Optional[time] = None
    preferred_end: Optional[time] = None
    min_session_minutes: int = Field(default=25, ge=1, le=24 * 60)
    max_session_minutes: int = Field(default=90, ge=1, le=24 * 60)
    splittable: bool = True
    flexible: bool = True
    dependencies: list[str] = Field(default_factory=list)
    project_name: Optional[str] = None

    @model_validator(mode="after")
    def validate_schedule_preferences(self):
        if any(day < 0 or day > 6 for day in self.preferred_days):
            raise ValueError("preferred_days must contain weekdays from 0 through 6")
        if self.min_session_minutes > self.max_session_minutes:
            raise ValueError("min_session_minutes cannot exceed max_session_minutes")
        if self.preferred_start and self.preferred_end and self.preferred_start >= self.preferred_end:
            raise ValueError("preferred_start must be before preferred_end")
        return self


class MilestoneIntent(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    deadline: Optional[date] = None
    sequence: int = Field(default=0, ge=0)


class ProjectIntent(StrictModel):
    name: str = Field(min_length=1, max_length=240)
    description: str = ""
    kind: Literal["project", "course"] = "project"
    total_sessions: int = Field(default=0, ge=0)
    session_minutes: int = Field(default=60, ge=1, le=24 * 60)
    target_deadline: Optional[date] = None
    milestones: list[MilestoneIntent] = Field(default_factory=list)
    tasks: list[TaskIntent] = Field(default_factory=list)


class CommitmentIntent(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    kind: Literal["fixed", "one_time", "weekly"] = "fixed"
    tag: Literal["university", "personal", "course", "project"] = "personal"
    recurrence: Literal["weekly", "once"] = "weekly"
    days_of_week: list[int] = Field(default_factory=list)
    start_time: time
    end_time: time
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    one_time_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_recurrence(self):
        if any(day < 0 or day > 6 for day in self.days_of_week):
            raise ValueError("days_of_week must contain weekdays from 0 through 6")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        if self.recurrence == "weekly" and not self.days_of_week:
            raise ValueError("weekly commitments require at least one weekday")
        if self.recurrence == "once" and self.one_time_date is None:
            raise ValueError("one-time commitments require one_time_date")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class PlanningConstraints(StrictModel):
    preferred_days: list[int] = Field(default_factory=list)
    unavailable_days: list[int] = Field(default_factory=list)
    earliest_start: Optional[time] = None
    latest_end: Optional[time] = None
    keep_workload_manageable: bool = True


class PlanningIntent(StrictModel):
    summary: str = ""
    projects: list[ProjectIntent] = Field(default_factory=list)
    tasks: list[TaskIntent] = Field(default_factory=list)
    commitments: list[CommitmentIntent] = Field(default_factory=list)
    constraints: PlanningConstraints = Field(default_factory=PlanningConstraints)
    clarifications: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class PlanningProposal(StrictModel):
    request_text: str = Field(min_length=1)
    source: Literal["gemini", "openrouter", "offline"]
    intent: PlanningIntent
    risk_level: Literal["low", "medium", "high"] = "low"


class ToolCall(StrictModel):
    name: str = Field(min_length=1)
    arguments: dict = Field(default_factory=dict)


class ToolResult(StrictModel):
    name: str
    success: bool
    data: object = None
    error: Optional[str] = None

