"""
Validates IncidentCommanderAgent executive summary synthesis:
- Runs full multi-agent pipeline
- Verifies executive_summary, critical_risks, action_plan keys exist
- Shows whether synthesis was AI-generated or deterministic fallback
"""
import asyncio, sys, json
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

# Mock shared infrastructure so we can run standalone
from unittest.mock import AsyncMock, patch, MagicMock

async def test():
    # Patch event bus and context store so no real WebSocket/DB is needed
    with patch('shared.event_bus.emit_agent_started', new=AsyncMock()), \
         patch('shared.event_bus.emit_agent_thinking', new=AsyncMock()), \
         patch('shared.event_bus.emit_agent_completed', new=AsyncMock()), \
         patch('shared.event_bus.emit_escalation', new=AsyncMock()), \
         patch('shared.event_bus.emit_plan_ready', new=AsyncMock()), \
         patch('shared.context_store.context_store.set_agent_output', new=AsyncMock()), \
         patch('shared.context_store.context_store.set_incident_state', new=AsyncMock()):

        from agents.incident_commander import IncidentCommanderAgent

        commander = IncidentCommanderAgent(incident_id="test-commander-001")

        incident_data = {
            "incoming_patients": 35,
            "icu_occupancy_pct": 88.0,
            "ed_occupancy_pct": 92.0,
            "total_icu_beds": 20,
            "available_icu_beds": 2,
            "available_nurses": 4,
            "available_ventilators": 2,
            "available_blood_units": 5,
        }

        print("Running full IncidentCommanderAgent pipeline...")
        result = await commander.run(incident_data)

        # Validate top-level run result
        assert result["status"] == "completed", f"FAIL: status={result['status']}"
        print(f"[COMMANDER STATUS ] {result['status']}")
        print(f"[SEVERITY         ] {result['output']['action_plan']['severity_label']}")
        print(f"[CONFIDENCE       ] {result['output']['confidence_score']}")
        print(f"[P1 ACTIONS       ] {len(result['output']['action_plan']['priority_1_actions'])}")
        print(f"[ESCALATIONS      ] {len(result['output']['action_plan']['escalation_items'])}")

        # Validate executive summary
        exec_sum = result["output"].get("executive_summary")
        assert exec_sum is not None, "FAIL: executive_summary key missing from output"

        print(f"\n[EXEC SUMMARY AI  ] ai_generated = {exec_sum.get('ai_generated')}")
        print(f"[EXEC NARRATIVE   ] {exec_sum['executive_summary'][:120]}...")
        print(f"[CRITICAL RISKS   ] {exec_sum['critical_risks']}")
        print(f"[ACTION PLAN ITEMS] {len(exec_sum['action_plan'])} items")

        assert "executive_summary" in exec_sum,  "FAIL: missing executive_summary"
        assert "critical_risks"    in exec_sum,  "FAIL: missing critical_risks"
        assert "action_plan"       in exec_sum,  "FAIL: missing action_plan"
        assert isinstance(exec_sum["critical_risks"], list), "FAIL: critical_risks not list"
        assert isinstance(exec_sum["action_plan"],    list), "FAIL: action_plan not list"

        print("\nIncidentCommanderAgent synthesis: ALL CHECKS PASSED")

asyncio.run(test())
