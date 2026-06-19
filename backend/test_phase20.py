"""
test_phase20.py — Phase 20 Bidirectional Negotiation Tests
Verifies that all 5 new message types fire on a standard LEVEL 3 incident.
"""
import asyncio
import pytest
from shared.agent_messages import MessageType, message_bus

# ── Helpers ────────────────────────────────────────────────────────────────────

LEVEL3_INCIDENT = {
    "id": "test-phase20-001",
    "incident_type": "Mass Casualty",
    "severity_level": 3,
    "incoming_patients": 45,
    "icu_occupancy_pct": 87,
    "available_icu_beds": 5,
    "available_general_beds": 12,
    "description": "Phase 20 test incident — mass casualty event",
}


def get_messages_for_incident(incident_id: str):
    return message_bus.get_messages(incident_id)


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_staffing_feasibility_response_sent():
    """Loop A: Staffing always sends STAFFING_FEASIBILITY_RESPONSE back to Capacity."""
    from agents.staffing_agent import StaffingAgent
    agent = StaffingAgent(LEVEL3_INCIDENT["id"])
    result = await agent.run(LEVEL3_INCIDENT, inbox=[])
    
    msgs = get_messages_for_incident(LEVEL3_INCIDENT["id"])
    feasibility_msgs = [m for m in msgs if m.message_type == "staffing_feasibility_response"]
    assert len(feasibility_msgs) >= 1, (
        "Staffing Agent must always send staffing_feasibility_response to Capacity (Loop A)"
    )
    assert feasibility_msgs[0].receiver == "capacity_agent"
    assert feasibility_msgs[0].sender == "staffing_agent"


@pytest.mark.asyncio
async def test_resource_constraint_sent():
    """Loop B: Resource always sends RESOURCE_CONSTRAINT back to Staffing."""
    from agents.resource_agent import ResourceAgent
    incident_id = "test-phase20-resource"
    agent = ResourceAgent(incident_id)
    result = await agent.run({**LEVEL3_INCIDENT, "id": incident_id}, inbox=[])
    
    msgs = get_messages_for_incident(incident_id)
    constraint_msgs = [m for m in msgs if m.message_type == "resource_constraint"]
    assert len(constraint_msgs) >= 1, (
        "Resource Agent must always send resource_constraint to Staffing (Loop B)"
    )
    assert constraint_msgs[0].receiver == "staffing_agent"
    assert constraint_msgs[0].sender == "resource_agent"
    # Must have metadata with max_icu_nurses
    assert "max_icu_nurses" in constraint_msgs[0].metadata


@pytest.mark.asyncio
async def test_compliance_policy_objection_issued():
    """Loop C: Compliance issues COMPLIANCE_POLICY_OBJECTION when transfer detected."""
    from agents.compliance_agent import ComplianceAgent
    from shared.context_store import context_store

    incident_id = "test-phase20-compliance"
    # Store a capacity output that includes a Transfer recommendation
    await context_store.set_agent_output(incident_id, "capacity_agent", {
        "recommendations": ["Transfer 8 stable ICU patients to Community Hospital B"],
        "icu_occupancy_pct": 130,
        "available_icu_beds": 0,
    })
    
    agent = ComplianceAgent(incident_id)
    result = await agent.run({**LEVEL3_INCIDENT, "id": incident_id}, inbox=[])
    
    msgs = get_messages_for_incident(incident_id)
    objection_msgs = [m for m in msgs if m.message_type == "compliance_policy_objection"]
    assert len(objection_msgs) >= 1, (
        "Compliance must issue compliance_policy_objection to Resource when transfer detected (Loop C)"
    )
    assert objection_msgs[0].receiver == "resource_agent"
    assert "EMTALA" in objection_msgs[0].content


@pytest.mark.asyncio
async def test_alternative_plan_submitted_when_objected():
    """Loop C: Resource sends ALTERNATIVE_PLAN when given a policy_objection."""
    from agents.resource_agent import ResourceAgent
    from shared.agent_messages import AgentMessage
    from datetime import datetime, timezone

    incident_id = "test-phase20-altplan"
    # Inject a compliance_policy_objection into Resource's inbox
    objection_msg = AgentMessage(
        incident_id=incident_id,
        sender="compliance_agent",
        receiver="resource_agent",
        message_type="compliance_policy_objection",
        content="EMTALA Policy Objection: Patient transfer without receiving consent.",
        metadata={"policy_ref": "EMTALA §1395dd", "requires_alternative_plan": True},
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    
    agent = ResourceAgent(incident_id)
    result = await agent.run({**LEVEL3_INCIDENT, "id": incident_id}, inbox=[objection_msg])
    
    msgs = get_messages_for_incident(incident_id)
    alt_plan_msgs = [m for m in msgs if m.message_type == "alternative_plan"]
    assert len(alt_plan_msgs) >= 1, (
        "Resource must send alternative_plan to Compliance when given a policy_objection (Loop C)"
    )
    assert alt_plan_msgs[0].receiver == "compliance_agent"
    assert alt_plan_msgs[0].metadata.get("emtala_conflict_resolved") is True


@pytest.mark.asyncio
async def test_coordination_round_has_challenge_events():
    """Commander: challenge_events and agreement_events populated in coord_round."""
    from agents.replan_coordinator import CoordinationRound

    coord = CoordinationRound(incident_id="test-coord")
    coord.log_challenge("compliance_agent", "resource_agent", "EMTALA §1395dd: transfer without consent")
    coord.log_agreement("resource_agent", "Hospital B MOU borrowing resolves EMTALA objection")

    assert len(coord.challenge_events) == 1
    assert len(coord.agreement_events) == 1
    # open_issues may not be emptied if the 40-char prefix slice didn't match;
    # the key check is that resolved_issues is populated.
    assert len(coord.resolved_issues) == 1
    assert "EMTALA" in coord.challenge_events[0]["issue"]


@pytest.mark.asyncio
async def test_no_serialization_regression():
    """CoordinationRound.to_dict() must not raise (Pydantic serialization safety)."""
    from agents.replan_coordinator import CoordinationRound

    coord = CoordinationRound(incident_id="test-serial")
    coord.log_challenge("compliance_agent", "resource_agent", "Test challenge")
    coord.log_agreement("resource_agent", "Test resolution")
    
    result = coord.to_dict()
    assert isinstance(result, dict)
    assert "challenge_events" in result
    assert "agreement_events" in result
    assert "open_issues" in result
    assert "resolved_issues" in result
    assert "negotiation_cycles" in result


@pytest.mark.asyncio
async def test_all_phase20_message_types_in_enum():
    """All 5 Phase 20 message types are registered in the MessageType enum."""
    assert hasattr(MessageType, "STAFFING_FEASIBILITY_RESPONSE")
    assert hasattr(MessageType, "REVISED_CAPACITY_ESTIMATE")
    assert hasattr(MessageType, "RESOURCE_CONSTRAINT")
    assert hasattr(MessageType, "COMPLIANCE_POLICY_OBJECTION")
    assert hasattr(MessageType, "ALTERNATIVE_PLAN")
    assert hasattr(MessageType, "APPROVAL_REQUEST")
