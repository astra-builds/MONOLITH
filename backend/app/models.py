from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class ProjectIn(BaseModel):
    name: str
    description: str = ""
    kind: str = "project"  # project/course
    total_sessions: int = 0
    session_minutes: int = 60
    target_deadline: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    total_sessions: Optional[int] = None
    session_minutes: Optional[int] = None
    target_deadline: Optional[str] = None

class TaskIn(BaseModel):
    project_id: Optional[int] = None
    title: str
    description: str = ""
    estimated_minutes: int = 60
    remaining_minutes: Optional[int] = None
    deadline: Optional[str] = None
    priority: int = 3
    preferred_days: List[int] = []
    preferred_start: Optional[str] = None
    preferred_end: Optional[str] = None
    min_session_minutes: int = 25
    max_session_minutes: int = 90
    splittable: bool = True
    flexible: bool = True
    dependencies: List[int] = []
    status: str = "todo"

class TaskUpdate(BaseModel):
    project_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_minutes: Optional[int] = None
    remaining_minutes: Optional[int] = None
    deadline: Optional[str] = None
    priority: Optional[int] = None
    preferred_days: Optional[List[int]] = None
    preferred_start: Optional[str] = None
    preferred_end: Optional[str] = None
    min_session_minutes: Optional[int] = None
    max_session_minutes: Optional[int] = None
    splittable: Optional[bool] = None
    flexible: Optional[bool] = None
    dependencies: Optional[List[int]] = None
    status: Optional[str] = None
    completed_at: Optional[str] = None

class CommitmentIn(BaseModel):
    title: str
    kind: str = "fixed"
    tag: str = "personal"
    recurrence: str = "weekly"
    days_of_week: List[int] = []
    start_time: str
    end_time: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    one_time_date: Optional[str] = None

class CommitmentUpdate(BaseModel):
    title: Optional[str] = None
    kind: Optional[str] = None
    tag: Optional[str] = None
    recurrence: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    one_time_date: Optional[str] = None

class BlockUpdate(BaseModel):
    title: Optional[str] = None
    tag: Optional[str] = None
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    locked: Optional[bool] = None

class SettingsUpdate(BaseModel):
    timezone: Optional[str] = None
    working_days: Optional[List[int]] = None
    working_start: Optional[str] = None
    working_end: Optional[str] = None
    default_session_minutes: Optional[int] = None
    min_break_minutes: Optional[int] = None
    max_daily_minutes: Optional[int] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_autonomy: Optional[Literal["suggestion", "assisted", "full"]] = None

class AIPlanRequest(BaseModel):
    text: str
    provider: Optional[str] = None
    model: Optional[str] = None

class AIConversationMessage(BaseModel):
    conversation_id: str = "default"
    text: str
    confirm: bool = False

class CourseGenerateRequest(BaseModel):
    project_id: Optional[int] = None
    title: str
    total_sessions: int
    session_minutes: int = 120
    frequency: str = "weekly"  # weekly
    day_of_week: int = 5  # Saturday
    start_date: Optional[str] = None
    half: bool = False
    deadline: Optional[str] = None


class ImportRequest(BaseModel):
    """Request body for importing data from an export JSON payload."""
    settings: Optional[List[dict]] = []
    projects: Optional[List[dict]] = []
    milestones: Optional[List[dict]] = []
    tasks: Optional[List[dict]] = []
    commitments: Optional[List[dict]] = []
    availability_rules: Optional[List[dict]] = []
    schedule_blocks: Optional[List[dict]] = []
