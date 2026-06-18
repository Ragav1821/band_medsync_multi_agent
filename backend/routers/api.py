"""
API Routers for Incidents, Agents, Action Plans, Dashboard, Simulation, and WebSocket.
"""
import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends
from typing import List, Optional
from shared.schemas import IncidentCreate, IncidentResponse, IncidentStatus, BandNotificationRequest
from shared.event_bus import ws_manager
from services.data_store import store
from services.simulation_engine import list_scenarios, get_scenario
from agents.incident_commander import IncidentCommanderAgent
from auth.jwt_auth import require_approver
from config.settings import settings

router = APIRouter()


# ── Incidents ──────────────────────────────────────────────────────────────

@router.post("/incidents", response_model=dict, status_code=201)
async def create_incident(incident: IncidentCreate, background_tasks: BackgroundTasks):
    """Create a new incident and trigger the multi-agent workflow."""
    incident_dict = incident.model_dump()
    new_incident = store.create_incident(incident_dict)
    incident_id = new_incident["id"]
    
    # Update status
    store.update_incident_status(incident_id, IncidentStatus.AGENTS_RUNNING)
    
    # Run agent workflow in background
    background_tasks.add_task(run_agent_workflow, incident_id, incident_dict)
    
    return {
        "incident": new_incident,
        "message": "Incident created. Multi-agent workflow activated.",
        "websocket_url": f"/ws/incidents/{incident_id}",
    }


@router.get("/incidents", response_model=List[dict])
async def list_incidents():
    """List all incidents."""
    return store.get_all_incidents()


@router.get("/incidents/{incident_id}", response_model=dict)
async def get_incident(incident_id: str):
    """Get a specific incident."""
    incident = store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/incidents/{incident_id}/resolve", response_model=dict)
async def resolve_incident(incident_id: str):
    """Mark an incident as resolved."""
    incident = store.update_incident_status(incident_id, IncidentStatus.RESOLVED)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


# ── Agent Runs ────────────────────────────────────────────────────────────

@router.get("/incidents/{incident_id}/agent-runs", response_model=List[dict])
async def get_agent_runs(incident_id: str):
    """Get all agent runs for an incident."""
    return store.get_agent_runs_for_incident(incident_id)


# ── Action Plans ──────────────────────────────────────────────────────────

@router.get("/incidents/{incident_id}/action-plan", response_model=dict)
async def get_action_plan(incident_id: str):
    """Get the action plan for an incident."""
    plan = store.get_action_plan(incident_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Action plan not yet available")
    return plan


@router.patch("/action-plans/{plan_id}/approve", response_model=dict)
async def approve_action_plan(
    plan_id: str,
    # P0-2: require authenticated user with approver role
    # P0-3: identity comes from verified JWT token, not a user-supplied string
    current_user: dict = Depends(require_approver),
):
    """
    Approve an action plan (human-in-the-loop).
    Requires a valid JWT token with role: OPERATIONS_MANAGER | COMPLIANCE_OFFICER | CHIEF_MEDICAL_OFFICER.
    Approver identity is sourced from the authenticated token — not from a query parameter.
    """
    # Build verified identity string from JWT claims
    approved_by = current_user.get("display_name", current_user.get("name", current_user["sub"]))

    plan = store.approve_action_plan(plan_id, approved_by)
    if not plan:
        raise HTTPException(status_code=404, detail="Action plan not found")
    
    # Update incident status
    store.update_incident_status(plan["incident_id"], IncidentStatus.PLAN_APPROVED)
    
    # Broadcast approval
    await ws_manager.broadcast_to_incident(plan["incident_id"], {
        "event_type": "plan:approved",
        "incident_id": plan["incident_id"],
        "plan_id": plan_id,
        "approved_by": approved_by,
        "approver_role": current_user.get("role"),
    })

    # Fire Band notification stub for each escalation item
    from services.band_service import send_escalation_to_band
    for item in plan.get("escalation_items", []):
        await send_escalation_to_band(
            incident_id=plan["incident_id"],
            plan_id=plan_id,
            message=item,
            approved_by=approved_by,
        )

    return plan


# ── Dashboard ─────────────────────────────────────────────────────────────

@router.get("/dashboard/metrics", response_model=dict)
async def get_dashboard_metrics():
    """Get KPI metrics for the command dashboard."""
    return store.get_dashboard_metrics()


# ── Audit Trail ───────────────────────────────────────────────────────────

@router.get("/audit-events", response_model=List[dict])
async def get_audit_events(incident_id: Optional[str] = None):
    """Get audit events, optionally filtered by incident."""
    if incident_id:
        return store.get_audit_events(incident_id)
    return store.get_all_audit_events()


# ── Phase 18: Agent Message Bus ───────────────────────────────────────────

@router.get("/incidents/{incident_id}/messages", response_model=List[dict])
async def get_incident_messages(incident_id: str):
    """
    Return the full inter-agent message log for an incident.
    Powers the Coordination Timeline and Collaboration Dashboard.
    """
    from shared.agent_messages import message_bus
    return message_bus.get_conversation_dicts(incident_id)


@router.get("/incidents/{incident_id}/coordination-stats", response_model=dict)
async def get_coordination_stats(incident_id: str):
    """
    Return collaboration statistics for an incident:
    message counts, active agents, message type breakdown.
    """
    from shared.agent_messages import message_bus
    msgs = message_bus.get_conversation(incident_id)
    
    by_sender: dict = {}
    by_type: dict = {}
    agent_pairs: list = []
    
    for m in msgs:
        by_sender[m.sender] = by_sender.get(m.sender, 0) + 1
        by_type[m.message_type] = by_type.get(m.message_type, 0) + 1
        agent_pairs.append({"from": m.sender, "to": m.receiver, "type": m.message_type})
    
    return {
        "incident_id": incident_id,
        "total_messages": len(msgs),
        "messages_by_sender": by_sender,
        "messages_by_type": by_type,
        "agent_pairs": agent_pairs,
        "collaboration_active": len(msgs) > 0,
    }


@router.get("/incidents/{incident_id}/coordination", response_model=dict)
async def get_coordination_round(incident_id: str):
    """
    Phase 19: Return current coordination round state for an incident.
    Includes negotiation status, revision count, and round history.
    """
    from services.data_store import store
    round_data = store.get_coordination_round(incident_id)
    if not round_data:
        # Return a default (incident may not have started yet)
        return {
            "incident_id": incident_id,
            "current_round": 1,
            "max_rounds": 3,
            "revision_count": 0,
            "replan_count": 0,
            "status": "initial",
            "final_approval_round": None,
            "negotiation_log": [],
        }
    return round_data


@router.get("/incidents/{incident_id}/revisions", response_model=list)
async def get_revision_history(incident_id: str):
    """
    Phase 19: Return all replanning cycles for an incident.
    Filters the negotiation_log to show only revision events.
    """
    from services.data_store import store
    round_data = store.get_coordination_round(incident_id)
    if not round_data:
        return []
    log = round_data.get("negotiation_log", [])
    revision_events = [e for e in log if e.get("event") in (
        "REVISION_REQUESTED", "REPLAN_REQUEST_ISSUED",
        "AGENTS_REVISED", "COMPLIANCE_RECHECKED",
        "APPROVED", "FORCE_FINALIZED",
    )]
    return revision_events

# ── Simulation ────────────────────────────────────────────────────────────

@router.get("/simulation/scenarios", response_model=List[dict])
async def get_simulation_scenarios():
    """List all pre-built simulation scenarios."""
    return [s.model_dump() for s in list_scenarios()]


@router.post("/simulation/run/{scenario_id}", response_model=dict, status_code=201)
async def run_simulation(scenario_id: str, background_tasks: BackgroundTasks):
    """Run a pre-built simulation scenario."""
    try:
        scenario = get_scenario(scenario_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    
    incident_dict = scenario.incident_data.model_dump()
    new_incident = store.create_incident(incident_dict)
    incident_id = new_incident["id"]
    store.update_incident_status(incident_id, IncidentStatus.AGENTS_RUNNING)
    
    background_tasks.add_task(run_agent_workflow, incident_id, incident_dict)
    
    return {
        "scenario": scenario.model_dump(),
        "incident": new_incident,
        "message": f"Simulation '{scenario.name}' started. Multi-agent workflow activated.",
        "websocket_url": f"/ws/incidents/{incident_id}",
    }


# ── Band Notifications ─────────────────────────────────────────────────────

@router.post("/notifications/band", response_model=dict, status_code=202)
async def send_band_notification(body: BandNotificationRequest):
    """
    Send an escalation notification to Band.
    P1-4: Accepts a typed BandNotificationRequest schema (was raw dict).
    """
    from services.band_service import send_escalation_to_band
    result = await send_escalation_to_band(
        incident_id=body.incident_id,
        plan_id=body.plan_id,
        message=body.message,
        approved_by=body.approved_by,
    )
    return result


# ── WebSocket ─────────────────────────────────────────────────────────────

@router.websocket("/ws/incidents/{incident_id}")
async def websocket_endpoint(websocket: WebSocket, incident_id: str):
    """WebSocket endpoint for real-time agent event streaming."""
    await ws_manager.connect(websocket, incident_id)
    try:
        # Send welcome message
        await websocket.send_json({
            "event_type": "connection:established",
            "incident_id": incident_id,
            "message": "Connected to MedSync AI incident stream",
        })
        
        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"event_type": "heartbeat"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, incident_id)


# ── Background Task: Agent Workflow ───────────────────────────────────────

async def run_agent_workflow(incident_id: str, incident_data: dict):
    """
    Background task that runs the full multi-agent workflow.
    P1-1: Entire workflow wrapped with asyncio.wait_for using settings.agent_timeout_seconds.

    After the IncidentCommanderAgent completes it:
    1. Saves the commander's own run record.
    2. Extracts the 4 specialist agent outputs embedded in action_plan.agent_outputs
       and saves a run record for each so GET /agent-runs returns all 5 agents.
    3. Persists the action plan (including executive_summary).
    4. Updates incident status to plan_ready.
    """
    try:
        commander = IncidentCommanderAgent(incident_id)

        # P1-1: Enforce workflow timeout — prevents indefinite hang if Band/Gemini stalls
        result = await asyncio.wait_for(
            commander.run(incident_data),
            timeout=settings.agent_timeout_seconds,
        )

        # ── 1. Save commander run ──────────────────────────────────────────
        store.save_agent_run_result(incident_id, "incident_commander", result)

        if result.get("status") == "completed":
            output = result.get("output", {})
            action_plan_data = output.get("action_plan", {})
            agent_outputs = action_plan_data.get("agent_outputs", {})

            # ── 2. Save each specialist agent run ─────────────────────────
            agent_name_map = {
                "capacity":   "capacity_agent",
                "staffing":   "staffing_agent",
                "resource":   "resource_agent",
                "compliance": "compliance_agent",
            }
            for key, agent_name in agent_name_map.items():
                agent_out = agent_outputs.get(key, {})
                if agent_out:
                    specialist_run = {
                        "status": "completed",
                        "started_at": result.get("started_at"),
                        "completed_at": result.get("completed_at"),
                        "duration_ms": result.get("duration_ms"),
                        "confidence_score": agent_out.get("confidence_score", 0.0),
                        "output": agent_out,
                        "reasoning_trace": [],
                    }
                    store.save_agent_run_result(incident_id, agent_name, specialist_run)

            # ── 3. Save action plan (includes executive_summary) ──────────
            store.save_action_plan(incident_id, output)

            # ── 3b. Phase 19: persist coordination round ──────────────────
            coord_round_data = action_plan_data.get("coordination_round")
            if coord_round_data:
                store.save_coordination_round(incident_id, coord_round_data)

            # ── 4. Update incident status ─────────────────────────────────
            store.update_incident_status(incident_id, IncidentStatus.PLAN_READY)

        else:
            store.update_incident_status(incident_id, IncidentStatus.ACTIVE)

    except asyncio.TimeoutError:
        # P1-1: Workflow exceeded agent_timeout_seconds — surface to frontend
        store.update_incident_status(incident_id, IncidentStatus.ACTIVE)
        await ws_manager.broadcast_to_incident(incident_id, {
            "event_type": "agent:error",
            "incident_id": incident_id,
            "error": f"Workflow timeout after {settings.agent_timeout_seconds}s. Gemini fallback may be active.",
        })

    except Exception as e:
        store.update_incident_status(incident_id, IncidentStatus.ACTIVE)
        await ws_manager.broadcast_to_incident(incident_id, {
            "event_type": "agent:error",
            "incident_id": incident_id,
            "error": str(e),
        })




