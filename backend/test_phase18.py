"""Phase 18 — End-to-end collaboration pipeline test."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_pipeline():
    from shared.agent_messages import message_bus, AgentMessage
    from agents.capacity_agent  import CapacityAgent
    from agents.staffing_agent  import StaffingAgent
    from agents.resource_agent  import ResourceAgent
    from agents.compliance_agent import ComplianceAgent

    incident_id = "phase18-test"
    incident_data = {
        "incoming_patients": 40,
        "icu_occupancy_pct": 91.0,
        "ed_occupancy_pct": 88.0,
        "available_nurses": 12,
        "available_ventilators": 3,
        "blood_bank_units": 60,
        "severity_level": 3,
        "total_icu_beds": 20,
    }

    print("=== Phase 18 Collaboration Pipeline Test ===\n")

    # Round 1
    cap = CapacityAgent(incident_id)
    cap_result = await cap.run(incident_data, inbox=[])
    print(f"[Round 1] Capacity: {cap_result['status']}")

    # Round 2
    staffing_inbox  = message_bus.get_messages(incident_id, receiver="staffing_agent")
    resource_inbox  = message_bus.get_messages(incident_id, receiver="resource_agent")
    print(f"[Round 2] Staffing inbox: {len(staffing_inbox)} msgs, Resource inbox: {len(resource_inbox)} msgs")

    stf = StaffingAgent(incident_id)
    res = ResourceAgent(incident_id)
    stf_result, res_result = await asyncio.gather(
        stf.run(incident_data, inbox=staffing_inbox),
        res.run(incident_data, inbox=resource_inbox),
    )
    print(f"[Round 2] Staffing: {stf_result['status']}, Resource: {res_result['status']}")

    # Round 3
    compliance_inbox = message_bus.get_messages(incident_id, receiver="compliance_agent")
    print(f"[Round 3] Compliance inbox: {len(compliance_inbox)} msgs")

    comp = ComplianceAgent(incident_id)
    comp_result = await comp.run(incident_data, inbox=compliance_inbox)
    print(f"[Round 3] Compliance: {comp_result['status']}")

    # All messages
    all_msgs = message_bus.get_conversation(incident_id)
    print(f"\n=== Total messages exchanged: {len(all_msgs)} ===")
    for m in all_msgs:
        print(f"  {m.sender:25} -> {m.receiver:25} [{m.message_type}]")
        print(f"    {m.content[:80]}{'...' if len(m.content) > 80 else ''}")

    assert len(all_msgs) >= 3, "Expected at least 3 inter-agent messages"
    senders = set(m.sender for m in all_msgs)
    receivers = set(m.receiver for m in all_msgs)
    print(f"\nSenders:   {sorted(senders)}")
    print(f"Receivers: {sorted(receivers)}")
    print("\n=== PASS: Phase 18 collaboration pipeline working ===")

asyncio.run(test_pipeline())
