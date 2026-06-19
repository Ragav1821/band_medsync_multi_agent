import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class IncidentType(str, Enum):
    MASS_CASUALTY = "mass_casualty"
    ER_OVERLOAD = "er_overload"
    ICU_SATURATION = "icu_saturation"
    RESOURCE_SHORTAGE = "resource_shortage"
    STAFF_SHORTAGE = "staff_shortage"
    CUSTOM = "custom"


class SeverityLevel(int, Enum):
    MINOR = 1
    MAJOR = 2
    CRITICAL = 3


class IncidentStatus(str, Enum):
    ACTIVE = "active"
    AGENTS_RUNNING = "agents_running"
    PLAN_READY = "plan_ready"
    PLAN_APPROVED = "plan_approved"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    ERROR = "error"


class AgentName(str, Enum):
    INCIDENT_COMMANDER = "incident_commander"
    CAPACITY = "capacity_agent"
    STAFFING = "staffing_agent"
    RESOURCE = "resource_agent"
    COMPLIANCE = "compliance_agent"


class AgentStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    THINKING = "thinking"
    COMPLETED = "completed"
    ERROR = "error"


# ── Incident Schemas ─────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    incident_type: IncidentType
    incoming_patients: int = Field(ge=0, le=500)
    icu_occupancy_pct: float = Field(ge=0, le=100)
    ed_occupancy_pct: float = Field(ge=0, le=100, default=70.0)
    available_nurses: int = Field(ge=0)
    available_ventilators: int = Field(ge=0)
    available_icu_beds: int = Field(ge=0, default=0)
    total_icu_beds: int = Field(ge=0, default=0)
    blood_bank_units: int = Field(ge=0, default=50)
    # P1-3: length limits prevent oversized payloads reaching Gemini prompts
    additional_context: Optional[str] = Field(None, max_length=500)
    reported_by: Optional[str] = Field("system", max_length=100)


class IncidentResponse(BaseModel):
    id: str
    incident_type: str
    severity_level: int
    status: str
    incoming_patients: int
    icu_occupancy_pct: float
    ed_occupancy_pct: float
    available_nurses: int
    available_ventilators: int
    available_icu_beds: int
    total_icu_beds: int
    blood_bank_units: int
    reported_by: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]
    metadata: Optional[Dict]

    class Config:
        from_attributes = True


# ── Agent Schemas ─────────────────────────────────────────────────────────────

class AgentRunResponse(BaseModel):
    id: str
    incident_id: str
    agent_name: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    confidence_score: Optional[float]
    output_data: Optional[Dict]
    reasoning_trace: Optional[List]

    class Config:
        from_attributes = True


class AgentOutput(BaseModel):
    agent_name: AgentName
    status: AgentStatus
    confidence_score: float
    summary: str
    findings: List[str]
    recommendations: List[str]
    flags: List[str]  # WARNING / CRITICAL flags
    raw_data: Optional[Dict] = None


# ── Action Plan Schemas ───────────────────────────────────────────────────────

class ActionItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str
    responsible_party: str
    timeline: str  # "immediate", "15 minutes", "1 hour"
    status: str = "pending"
    is_compliant: bool = True
    compliance_note: Optional[str] = None


class ActionPlanResponse(BaseModel):
    id: str
    incident_id: str
    status: str
    priority_1_actions: Optional[List[ActionItem]]
    priority_2_actions: Optional[List[ActionItem]]
    priority_3_actions: Optional[List[ActionItem]]
    escalation_items: Optional[List[str]]
    compliance_status: str
    overall_summary: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ── WebSocket Event Schemas ───────────────────────────────────────────────────

class WSEvent(BaseModel):
    event_type: str
    incident_id: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Dashboard Schemas ─────────────────────────────────────────────────────────

class DashboardMetrics(BaseModel):
    total_incidents_today: int
    active_incidents: int
    resolved_incidents: int
    critical_incidents: int
    avg_response_time_minutes: float
    agent_runs_today: int
    compliance_rate_pct: float
    capacity_alerts: int


# ── Simulation Schemas ────────────────────────────────────────────────────────

class SimulationScenario(BaseModel):
    id: str
    name: str
    description: str
    severity_label: str
    incident_data: IncidentCreate
    tags: List[str]


# ── Band Notification Schema (P1-4) ──────────────────────────────────────────

class BandNotificationRequest(BaseModel):
    """Typed schema for POST /notifications/band — replaces raw dict."""
    incident_id: str = Field(..., max_length=64, description="UUID of the incident")
    plan_id: str = Field("", max_length=64)
    message: str = Field(..., min_length=1, max_length=1000)
    approved_by: str = Field("system", max_length=100)


# ── Phase 20: Video Generator Schemas ────────────────────────────────────────

class VideoJobStatus(str, Enum):
    PENDING    = "pending"
    STORY      = "story"
    SCRIPT     = "script"
    STORYBOARD = "storyboard"
    AUDIO      = "audio"
    VISUALS    = "visuals"
    COMPOSING  = "composing"
    COMPLETED  = "completed"
    FAILED     = "failed"


class VideoGenerateRequest(BaseModel):
    """Request body for POST /incidents/{id}/generate-video."""
    incident_id: str = Field(..., max_length=64)
    voice_provider: str = Field(
        "edge_tts",
        description="edge_tts (default, neural) | gtts (free fallback) | elevenlabs (premium)",
    )
    resolution: str = Field("1280x720", description="Video resolution")
    target_duration_sec: int = Field(120, ge=60, le=300, description="Target duration in seconds")


class VideoJobSchema(BaseModel):
    """Full video generation job record."""
    id: str
    incident_id: str
    status: VideoJobStatus
    progress_pct: int = 0
    story_json: Optional[Dict] = None
    script_json: Optional[Dict] = None
    storyboard_json: Optional[Dict] = None
    output_path: Optional[str] = None
    audio_path: Optional[str] = None
    duration_sec: Optional[float] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

    class Config:
        from_attributes = True
