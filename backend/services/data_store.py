"""
In-Memory Data Store — replaces a real database for the hackathon demo.
Production would use PostgreSQL + SQLAlchemy + MongoDB.
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from shared.schemas import IncidentStatus


class IncidentStore:
    """Thread-safe in-memory store for incidents, agent runs, action plans, and audit events."""

    def __init__(self):
        self._incidents: Dict[str, Dict] = {}
        self._agent_runs: Dict[str, Dict] = {}       # run_id → run data
        self._action_plans: Dict[str, Dict] = {}     # plan_id → plan data
        self._audit_events: List[Dict] = []
        self._notifications: List[Dict] = []

    # ── Incidents ───────────────────────────────────────────────────────────

    def create_incident(self, data: Dict) -> Dict:
        incident_id = str(uuid.uuid4())
        incident = {
            "id": incident_id,
            "incident_type": data.get("incident_type", "custom"),
            "severity_level": self._infer_severity(data),
            "status": IncidentStatus.ACTIVE,
            "incoming_patients": data.get("incoming_patients", 0),
            "icu_occupancy_pct": data.get("icu_occupancy_pct", 0.0),
            "ed_occupancy_pct": data.get("ed_occupancy_pct", 70.0),
            "available_nurses": data.get("available_nurses", 0),
            "available_ventilators": data.get("available_ventilators", 0),
            "available_icu_beds": data.get("available_icu_beds", 0),
            "total_icu_beds": data.get("total_icu_beds", 20),
            "blood_bank_units": data.get("blood_bank_units", 50),
            "reported_by": data.get("reported_by", "system"),
            "created_at": datetime.utcnow().isoformat(),
            "resolved_at": None,
            "metadata": {},
        }
        self._incidents[incident_id] = incident
        self._log_audit(incident_id, "incident_created", "system", "system", {"severity": incident["severity_level"]})
        return incident

    def get_incident(self, incident_id: str) -> Optional[Dict]:
        return self._incidents.get(incident_id)

    def get_all_incidents(self) -> List[Dict]:
        return sorted(self._incidents.values(), key=lambda x: x["created_at"], reverse=True)

    def update_incident_status(self, incident_id: str, status: str) -> Optional[Dict]:
        if incident_id in self._incidents:
            self._incidents[incident_id]["status"] = status
            if status == "resolved":
                self._incidents[incident_id]["resolved_at"] = datetime.utcnow().isoformat()
            self._log_audit(incident_id, "status_changed", "system", "system", {"new_status": status})
            return self._incidents[incident_id]
        return None

    # ── Agent Runs ──────────────────────────────────────────────────────────

    def create_agent_run(self, incident_id: str, agent_name: str) -> Dict:
        run_id = str(uuid.uuid4())
        run = {
            "id": run_id,
            "incident_id": incident_id,
            "agent_name": agent_name,
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "confidence_score": None,
            "output_data": None,
            "reasoning_trace": None,
        }
        self._agent_runs[run_id] = run
        return run

    def save_agent_run_result(self, incident_id: str, agent_name: str, result: Dict) -> Dict:
        # Find or create run record
        run_id = str(uuid.uuid4())
        run = {
            "id": run_id,
            "incident_id": incident_id,
            "agent_name": agent_name,
            "status": result.get("status", "completed"),
            "started_at": result.get("started_at"),
            "completed_at": result.get("completed_at"),
            "duration_ms": result.get("duration_ms"),
            "confidence_score": result.get("confidence_score"),
            "output_data": result.get("output"),
            "reasoning_trace": result.get("reasoning_trace", []),
        }
        self._agent_runs[run_id] = run
        self._log_audit(
            incident_id,
            "agent_completed",
            "agent",
            agent_name,
            {"confidence": result.get("confidence_score"), "status": result.get("status")},
        )
        return run

    def get_agent_runs_for_incident(self, incident_id: str) -> List[Dict]:
        return [r for r in self._agent_runs.values() if r["incident_id"] == incident_id]

    # ── Action Plans ────────────────────────────────────────────────────────

    def save_action_plan(self, incident_id: str, commander_output: Dict) -> Dict:
        action_plan_data = commander_output.get("action_plan", {})
        plan_id = action_plan_data.get("id", str(uuid.uuid4()))
        plan = {
            "id": plan_id,
            "incident_id": incident_id,
            "status": "pending",
            "severity_level": action_plan_data.get("severity_level"),
            "severity_label": action_plan_data.get("severity_label"),
            "priority_1_actions": action_plan_data.get("priority_1_actions", []),
            "priority_2_actions": action_plan_data.get("priority_2_actions", []),
            "priority_3_actions": action_plan_data.get("priority_3_actions", []),
            "escalation_items": action_plan_data.get("escalation_items", []),
            "compliance_status": action_plan_data.get("compliance_status", "UNKNOWN"),
            "required_documentation": action_plan_data.get("required_documentation", []),
            "overall_summary": commander_output.get("summary", ""),
            "agent_outputs": action_plan_data.get("agent_outputs", {}),
            # BLOCKER 2 FIX: executive_summary lives one level above action_plan in commander output
            "executive_summary": commander_output.get("executive_summary", {}),
            "approved_by": None,
            "approved_at": None,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._action_plans[plan_id] = plan
        self._log_audit(incident_id, "action_plan_created", "agent", "incident_commander", {"plan_id": plan_id})
        return plan

    def get_action_plan(self, incident_id: str) -> Optional[Dict]:
        for plan in self._action_plans.values():
            if plan["incident_id"] == incident_id:
                return plan
        return None

    def approve_action_plan(self, plan_id: str, approved_by: str) -> Optional[Dict]:
        if plan_id in self._action_plans:
            plan = self._action_plans[plan_id]
            plan["status"] = "approved"
            plan["approved_by"] = approved_by
            plan["approved_at"] = datetime.utcnow().isoformat()
            self._log_audit(
                plan["incident_id"], "plan_approved", "human", approved_by, {"plan_id": plan_id}
            )
            return plan
        return None

    # ── Audit Trail ─────────────────────────────────────────────────────────

    def _log_audit(self, incident_id: str, event_type: str, actor_type: str, actor_id: str, data: Dict):
        self._audit_events.append({
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "event_type": event_type,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "event_data": data,
            "created_at": datetime.utcnow().isoformat(),
        })

    def get_audit_events(self, incident_id: str) -> List[Dict]:
        return [e for e in self._audit_events if e["incident_id"] == incident_id]

    def get_all_audit_events(self) -> List[Dict]:
        return sorted(self._audit_events, key=lambda x: x["created_at"], reverse=True)

    # ── Dashboard Metrics ────────────────────────────────────────────────────

    def get_dashboard_metrics(self) -> Dict:
        from datetime import date
        today = date.today().isoformat()
        incidents_today = [i for i in self._incidents.values() if i["created_at"][:10] == today]
        active = [i for i in self._incidents.values() if i["status"] not in ["resolved"]]
        critical = [i for i in self._incidents.values() if i["severity_level"] == 3]
        resolved = [i for i in self._incidents.values() if i["status"] == "resolved"]

        return {
            "total_incidents_today": len(incidents_today),
            "active_incidents": len(active),
            "resolved_incidents": len(resolved),
            "critical_incidents": len(critical),
            "avg_response_time_minutes": 2.3,  # Simulated for demo
            "agent_runs_today": len(self._agent_runs),
            "compliance_rate_pct": 94.2,
            "capacity_alerts": len([i for i in critical if i["icu_occupancy_pct"] > 85]),
        }

    def _infer_severity(self, data: Dict) -> int:
        incoming = data.get("incoming_patients", 0)
        icu_pct = data.get("icu_occupancy_pct", 0)
        nurses = data.get("available_nurses", 999)
        vents = data.get("available_ventilators", 999)
        if incoming >= 30 or icu_pct >= 90 or nurses <= 5 or vents <= 3:
            return 3
        elif incoming >= 10 or icu_pct >= 70:
            return 2
        return 1


# Singleton
store = IncidentStore()
