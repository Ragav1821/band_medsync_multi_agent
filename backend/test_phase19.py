"""
Phase 19A — Negotiation Loop End-to-End Test

Scenario: available_ventilators=1, available_nurses=4, incoming_patients=50,
icu_occupancy_pct=95 → forces REQUIRES_REVIEW from Compliance
→ REVISION_REQUEST → replan loop → revised plans → resolution.

Run:
    python test_phase19.py
"""
import asyncio
import logging
import sys
import os

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("test_phase19")


# ── Incident data designed to force REQUIRES_REVIEW ───────────────────────────
# Need > 2 compliance_issues for REQUIRES_REVIEW status.
# Sources of compliance issues:
#   1. Staffing ratio exception (ratio < 0.7)
#   2. CMO authorization needed (still_short > 0)
#   3. EMTALA diversion (projected_icu_pct > 100)
INCIDENT_DATA = {
    "incident_type": "mass_casualty",
    "incoming_patients": 60,          # High volume → big gaps
    "icu_occupancy_pct": 98,          # Near full → projected > 100% → EMTALA diversion issue
    "ed_occupancy_pct": 90,
    "available_nurses": 2,            # Extreme shortage → ratio well below 0.7 + unresolvable gap
    "available_ventilators": 0,       # Zero → massive resource gap
    "available_icu_beds": 1,
    "total_icu_beds": 20,
    "blood_bank_units": 10,           # Low → blood gap adds another issue context
    "severity_level": 3,
}


async def run_test():
    from shared.agent_messages import message_bus, MessageType
    from agents.incident_commander import IncidentCommanderAgent

    incident_id = "test-phase19-negotiation"

    # Clear any stale messages from previous runs
    message_bus.clear_incident_messages(incident_id)

    logger.info("=" * 70)
    logger.info("Phase 19A Negotiation Loop Test")
    logger.info("=" * 70)
    logger.info("Incident: %s", incident_id)
    logger.info("Data: vents=%d, nurses=%d, incoming=%d, icu=%d%%",
                INCIDENT_DATA["available_ventilators"],
                INCIDENT_DATA["available_nurses"],
                INCIDENT_DATA["incoming_patients"],
                INCIDENT_DATA["icu_occupancy_pct"])
    logger.info("-" * 70)

    # Run the full commander workflow
    commander = IncidentCommanderAgent(incident_id)
    result = await commander.run(INCIDENT_DATA)

    # ── Extract results ─────────────────────────────────────────────────────────
    output = result.get("output", {})
    action_plan = output.get("action_plan", {})
    coord_round = action_plan.get("coordination_round", {})
    all_msgs = message_bus.get_conversation(incident_id)

    logger.info("-" * 70)
    logger.info("RESULTS")
    logger.info("-" * 70)
    logger.info("Commander status: %s", result.get("status"))
    logger.info("Coordination round status: %s", coord_round.get("status"))
    logger.info("Replan count: %d", coord_round.get("replan_count", 0))
    logger.info("Revision count: %d", coord_round.get("revision_count", 0))
    logger.info("Final approval round: %s", coord_round.get("final_approval_round"))
    logger.info("Negotiation log entries: %d", len(coord_round.get("negotiation_log", [])))
    logger.info("Total inter-agent messages: %d", len(all_msgs))

    # ── Print negotiation log ───────────────────────────────────────────────────
    logger.info("-" * 70)
    logger.info("NEGOTIATION LOG")
    for entry in coord_round.get("negotiation_log", []):
        logger.info("  Round %d | %-24s | %s",
                     entry["round"], entry["event"], entry["detail"][:80])

    # ── Print all messages ──────────────────────────────────────────────────────
    logger.info("-" * 70)
    logger.info("ALL INTER-AGENT MESSAGES")
    for msg in all_msgs:
        logger.info("  %s → %s [%s]: %s",
                     msg.sender[:15].ljust(15),
                     msg.receiver[:15].ljust(15),
                     msg.message_type,
                     msg.content[:70])

    # ── Assertions ──────────────────────────────────────────────────────────────
    logger.info("-" * 70)
    logger.info("ASSERTIONS")
    errors = []

    # A1: Commander completed successfully
    if result.get("status") != "completed":
        errors.append(f"A1 FAIL: Commander status={result.get('status')}, expected 'completed'")
    else:
        logger.info("  ✅ A1: Commander completed successfully")

    # A2: Coordination round has replan_count >= 1
    if coord_round.get("replan_count", 0) < 1:
        errors.append(f"A2 FAIL: replan_count={coord_round.get('replan_count', 0)}, expected >= 1")
    else:
        logger.info("  ✅ A2: replan_count=%d (>= 1)", coord_round.get("replan_count", 0))

    # A3: Final status is approved or force_finalized (not stuck in replanning)
    final_status = coord_round.get("status", "unknown")
    if final_status not in ("approved", "force_finalized"):
        errors.append(f"A3 FAIL: coord status='{final_status}', expected 'approved' or 'force_finalized'")
    else:
        logger.info("  ✅ A3: final status='%s'", final_status)

    # A4: revision_request message exists from compliance_agent
    revision_msgs = [m for m in all_msgs
                     if m.message_type == MessageType.REVISION_REQUEST
                     and m.sender == "compliance_agent"]
    if not revision_msgs:
        errors.append("A4 FAIL: No revision_request message found from compliance_agent")
    else:
        logger.info("  ✅ A4: %d revision_request(s) from compliance_agent", len(revision_msgs))

    # A5: replan_request messages from commander to resource + staffing
    replan_to_resource = [m for m in all_msgs
                          if m.message_type == MessageType.REPLAN_REQUEST
                          and m.receiver == "resource_agent"]
    replan_to_staffing = [m for m in all_msgs
                          if m.message_type == MessageType.REPLAN_REQUEST
                          and m.receiver == "staffing_agent"]
    if not replan_to_resource:
        errors.append("A5a FAIL: No replan_request to resource_agent")
    else:
        logger.info("  ✅ A5a: %d replan_request(s) to resource_agent", len(replan_to_resource))
    if not replan_to_staffing:
        errors.append("A5b FAIL: No replan_request to staffing_agent")
    else:
        logger.info("  ✅ A5b: %d replan_request(s) to staffing_agent", len(replan_to_staffing))

    # A6: replan_response messages exist
    replan_responses = [m for m in all_msgs
                        if m.message_type == MessageType.REPLAN_RESPONSE]
    if not replan_responses:
        errors.append("A6 FAIL: No replan_response messages found")
    else:
        logger.info("  ✅ A6: %d replan_response(s) found", len(replan_responses))

    # A7: Negotiation log has key events
    log_events = {e["event"] for e in coord_round.get("negotiation_log", [])}
    expected_events = {"REVISION_REQUESTED", "REPLAN_REQUEST_ISSUED", "AGENTS_REVISED", "COMPLIANCE_RECHECKED"}
    missing_events = expected_events - log_events
    if missing_events:
        errors.append(f"A7 FAIL: Missing negotiation log events: {missing_events}")
    else:
        logger.info("  ✅ A7: All expected negotiation log events present: %s", expected_events)

    # A8: At least one replan_response has gap_resolved or alternative_coverage_applied
    resolved_responses = [m for m in replan_responses
                          if m.metadata.get("gap_resolved") or m.metadata.get("alternative_coverage_applied")]
    if not resolved_responses:
        errors.append("A8 FAIL: No replan_response with gap_resolved or alternative_coverage_applied")
    else:
        logger.info("  ✅ A8: %d replan_response(s) show gap resolution", len(resolved_responses))

    # ── Final verdict ──────────────────────────────────────────────────────────
    logger.info("=" * 70)
    if errors:
        for e in errors:
            logger.error("  ❌ %s", e)
        logger.error("RESULT: %d assertion(s) FAILED", len(errors))
        sys.exit(1)
    else:
        logger.info("  ✅ ALL ASSERTIONS PASSED — Negotiation loop works correctly!")
        logger.info("  Classification: COLLABORATIVE (agents challenge, revise, and converge)")
        logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_test())
