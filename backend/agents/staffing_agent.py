"""
Staffing Agent — Monitors staff availability, detects shortages, recommends staffing actions.
Phase 18: Reads capacity_alert from Capacity Agent to refine ICU nurse calculation.
         Sends staffing_gap to Resource Agent for equipment-nurse coordination.
Phase 19: Handles REPLAN_REQUEST from Commander — proposes alternative shift coverage
         and sends REPLAN_RESPONSE back to Compliance.
Phase 20: Loop A: Always sends STAFFING_FEASIBILITY_RESPONSE back to Capacity Agent.
         Loop B: Reads RESOURCE_CONSTRAINT from Resource Agent and revises ICU deployment.
"""
import asyncio
from typing import Dict, List
from agents.base_agent import AgentBase


class StaffingAgent(AgentBase):
    agent_name = "staffing_agent"
    agent_role = "Staffing Analysis Agent"
    agent_description = (
        "Monitors staff availability, detects ratio violations, "
        "and recommends staffing actions including on-call activations."
    )

    # Safe nurse:patient ratios
    ICU_RATIO = 1
    ED_RATIO = 1
    GENERAL_RATIO = 1

    async def analyze(self, incident_data: Dict, inbox: list = None) -> Dict:
        incoming = incident_data.get("incoming_patients", 0)
        available_nurses = incident_data.get("available_nurses", 0)
        icu_pct = incident_data.get("icu_occupancy_pct", 0.0)
        total_icu_beds = incident_data.get("total_icu_beds", 20)

        findings = []
        recommendations = []
        flags = []

        # ── Phase 18: Consume Capacity Agent's capacity_alert ─────────────────
        inbox = inbox or []
        capacity_msgs = [m for m in inbox if m.message_type == "capacity_alert"]

        # ── Phase 19: Detect REPLAN_REQUEST from Commander ───────────────────
        replan_msgs  = [m for m in inbox if m.message_type == "replan_request"]
        replan_mode  = bool(replan_msgs)
        replan_round = replan_msgs[-1].metadata.get("replan_round", 0) if replan_msgs else 0

        capacity_context = {}
        if capacity_msgs:
            latest = capacity_msgs[-1]
            capacity_context = latest.metadata
            projected_icu = capacity_context.get("projected_icu_pct", icu_pct)
            cap_nurse_ask = capacity_context.get("icu_nurses_needed", 0)
            await self._emit_thinking(
                "CAPACITY_INPUT",
                f"Received from Capacity Agent: ICU projected {projected_icu:.1f}%. "
                f"Capacity requests {cap_nurse_ask} additional ICU nurses — factoring into gap analysis."
            )
            findings.append(
                f"Capacity Agent alert: ICU projected at {projected_icu:.1f}% — "
                f"cross-agent coordination active."
            )
        else:
            cap_nurse_ask = 0

        # ── Phase 20 Loop B: Detect RESOURCE_CONSTRAINT from Resource Agent ──────
        # Resource sends this after analyzing staffing_gap to cap deployment numbers
        resource_constraint_msgs = [m for m in inbox if m.message_type == "resource_constraint"]
        resource_constraint = None
        max_icu_nurses_from_resource = None
        if resource_constraint_msgs:
            rc_meta = resource_constraint_msgs[-1].metadata
            max_icu_nurses_from_resource = rc_meta.get("max_icu_nurses", None)
            await self._emit_thinking(
                "RESOURCE_CONSTRAINT_RECEIVED",
                f"⇦ Resource Agent constrained ICU deployment: max {max_icu_nurses_from_resource} nurses "
                f"(physical workstation limit). Revising ICU allocation strategy."
            )
            findings.append(
                f"Resource Agent constraint: ICU physical capacity limits deployment to "
                f"{max_icu_nurses_from_resource} nurses max — revising allocation."
            )
            resource_constraint = resource_constraint_msgs[-1]


        if replan_mode:
            await self._emit_thinking(
                "REPLAN_MODE",
                f"[REPLAN ROUND {replan_round}] Commander requests revised staffing plan. "
                f"Evaluating alternative shift coverage: extended shifts, cross-unit redeployment, "
                f"float pool activation, and retired nurse emergency recall.",
            )
            findings.append(
                f"[REPLAN {replan_round}] Commander requested staffing revision — "
                f"applying alternative coverage strategies."
            )

        # Step 1: Calculate required staffing
        await self._emit_thinking("STAFFING_CALC", "Calculating required nurse staffing for surge scenario...")


        icu_patients    = int(total_icu_beds * icu_pct / 100)
        ed_patients_est = int(incoming * 0.8)

        required_icu_nurses     = max(1, icu_patients // 2)
        required_ed_nurses      = max(1, ed_patients_est // 3)
        required_general_nurses = max(1, (incoming - ed_patients_est) // 4)

        # Boost ICU nurses if Capacity Agent requested more
        required_icu_nurses = max(required_icu_nurses, required_icu_nurses + cap_nurse_ask)

        # Phase 20 Loop B: Cap ICU nurses if Resource reported workstation limit
        if max_icu_nurses_from_resource is not None and required_icu_nurses > max_icu_nurses_from_resource:
            overflow_icu = required_icu_nurses - max_icu_nurses_from_resource
            required_icu_nurses = max_icu_nurses_from_resource
            findings.append(
                f"ICU nurse deployment capped at {required_icu_nurses} (Resource workstation limit). "
                f"{overflow_icu} nurses redirected to overflow ward."
            )
            recommendations.insert(0, f"Redirect {overflow_icu} nurses from ICU to overflow wards (Resource capacity constraint)")

        total_required = required_icu_nurses + required_ed_nurses + required_general_nurses

        findings.append(f"Current available nurses: {available_nurses}")
        findings.append(f"Required for ICU ({icu_patients} patients): {required_icu_nurses} nurses")
        findings.append(f"Required for ED surge ({ed_patients_est} patients): {required_ed_nurses} nurses")
        findings.append(f"Required for general wards: {required_general_nurses} nurses")
        findings.append(f"Total nurses required: {total_required}")

        # Step 2: Gap analysis
        await self._emit_thinking("GAP_ANALYSIS", f"Detecting staffing gaps: need {total_required}, have {available_nurses}...")

        gap = total_required - available_nurses
        if gap > 0:
            findings.append(f"STAFFING GAP: {gap} nurses short")
            flags.append(f"⚠️ CRITICAL: {gap}-nurse shortage detected")
        else:
            findings.append("Staffing levels adequate for surge")

        # Step 3: On-call analysis
        await self._emit_thinking("ONCALL_CHECK", "Checking on-call nurse availability pool...")

        on_call_available = min(gap, 6) if gap > 0 else 0
        agency_available  = min(max(0, gap - on_call_available), 8)

        # Phase 19: In replan mode, unlock additional alternative coverage
        if replan_mode and gap > 0:
            # Alternative strategies: float pool, extended shifts, retired nurse recall
            float_pool_available = min(max(0, gap - on_call_available - agency_available), 4)
            extended_shift_nurses = min(max(0, gap - on_call_available - agency_available - float_pool_available), 3)
            still_short = max(0, gap - on_call_available - agency_available - float_pool_available - extended_shift_nurses)
            if float_pool_available > 0:
                recommendations.insert(0, f"Activate hospital float pool: {float_pool_available} nurses available immediately")
            if extended_shift_nurses > 0:
                recommendations.insert(1, f"Authorise {extended_shift_nurses} voluntary extended 12-hr shifts (current staff)")
            findings.append(
                f"[REPLAN {replan_round}] Alternative coverage: float pool ({float_pool_available}) + "
                f"extended shifts ({extended_shift_nurses}) reduces unresolved gap."
            )
        else:
            float_pool_available = 0
            extended_shift_nurses = 0
            still_short = max(0, gap - on_call_available - agency_available)

        if on_call_available > 0:
            recommendations.append(f"Activate {on_call_available} on-call nurses immediately (30-min ETA)")
        if agency_available > 0:
            recommendations.append(f"Request {agency_available} agency nurses from registered staffing pool (60-min ETA)")
        if still_short > 0:
            recommendations.append(
                f"Authorize mandatory overtime for {still_short} additional nurses — requires CMO approval"
            )
            flags.append(f"🚨 ESCALATION: {still_short} nurses unresolvable without executive authorization")
        elif replan_mode and gap > 0:
            findings.append(f"[REPLAN] Staffing gap FULLY RESOLVED via alternative coverage strategies.")

        # Step 4: Shift allocation
        await self._emit_thinking("ALLOCATION", "Calculating optimal nurse allocation by unit...")

        recommendations.append(f"Allocate {required_icu_nurses} nurses to ICU (priority: ventilated patients)")
        recommendations.append(f"Allocate {min(available_nurses, required_ed_nurses)} nurses to ED triage")

        # Step 5: Ratio compliance check
        await self._emit_thinking("RATIO_CHECK", "Verifying nurse-patient ratios against safe care standards...")

        total_covered = available_nurses + on_call_available + agency_available + float_pool_available + extended_shift_nurses
        effective_ratio = total_covered / max(1, total_required)
        if effective_ratio < 0.7:
            flags.append("⚠️ WARNING: Nurse:patient ratio below safe thresholds until on-call staff arrives")
            recommendations.append("Document temporary ratio exception with medical necessity justification")

        confidence_score = 0.90 if replan_mode else 0.88

        # ── Phase 18/19/20: Send messages to peer agents ──────────────────────
        # Phase 20 Loop A: ALWAYS send STAFFING_FEASIBILITY_RESPONSE back to Capacity
        # This creates the bidirectional Capacity ↔ Staffing channel regardless of replan state.
        nurses_coverable = on_call_available + agency_available + float_pool_available + extended_shift_nurses + available_nurses
        nurses_coverable = min(nurses_coverable, total_required)
        icu_risk_delta_pct = None
        if capacity_context:
            projected_icu = capacity_context.get("projected_icu_pct", 0)
            cap_ask = capacity_context.get("icu_nurses_needed", 0)
            nurses_fulfilled = min(cap_ask, on_call_available + agency_available)
            # Every additional ICU nurse reduces projected ICU % by ~1.5pp (heuristic)
            icu_risk_delta_pct = round(nurses_fulfilled * 1.5, 1)
            revised_icu_risk = max(85.0, projected_icu - icu_risk_delta_pct)
        else:
            revised_icu_risk = None
            icu_risk_delta_pct = 0

        await self.send_message(
            receiver="capacity_agent",
            message_type="staffing_feasibility_response",
            content=(
                f"Staffing feasibility: can deploy {nurses_coverable} of {total_required} required nurses. "
                f"{on_call_available} on-call + {agency_available} agency activated. "
                f"{f'ICU risk reduction: -{icu_risk_delta_pct}pp (projected → {revised_icu_risk:.1f}%).' if revised_icu_risk else ''} "
                f"{'Gap of ' + str(still_short) + ' nurses unresolvable without CMO auth.' if still_short > 0 else 'Full staffing gap resolved.'}"
            ),
            metadata={
                "nurses_coverable": nurses_coverable,
                "total_required": total_required,
                "still_short": still_short,
                "on_call_activated": on_call_available,
                "agency_requested": agency_available,
                "icu_risk_delta_pct": icu_risk_delta_pct,
                "revised_icu_risk_pct": revised_icu_risk,
                "gap_fully_resolved": still_short == 0,
                "resource_constraint_applied": resource_constraint is not None,
            },
        )

        # Message → Resource: ICU beds need equipment support
        icu_beds_needed = required_icu_nurses
        msg_type = "replan_response" if replan_mode else "staffing_gap"
        msg_prefix = f"[REPLAN {replan_round}] REVISED PLAN: " if replan_mode else ""

        await self.send_message(
            receiver="resource_agent",
            message_type=msg_type,
            content=(
                f"{msg_prefix}Staffing gap of {gap} nurses. "
                f"Activating {on_call_available} on-call + {agency_available} agency"
                f"{f' + {float_pool_available} float pool + {extended_shift_nurses} extended shifts' if replan_mode else ''} nurses. "
                f"ICU requires {required_icu_nurses} nurses for {icu_patients} patients — "
                f"ensure ventilator and equipment support for {icu_beds_needed} ICU positions."
            ),
            metadata={
                "total_gap": gap,
                "on_call_activated": on_call_available,
                "agency_requested": agency_available,
                "float_pool": float_pool_available,
                "extended_shifts": extended_shift_nurses,
                "still_short": still_short,
                "icu_nurses_required": required_icu_nurses,
                "requires_escalation": still_short > 0,
                "icu_beds_to_equip": icu_beds_needed,
                "replan_round": replan_round,
                "replan_mode": replan_mode,
                "gap_resolved": replan_mode and still_short == 0,
            },
        )

        # Message → Compliance: ratio violation / or replan resolution
        if effective_ratio < 0.7 or still_short > 0:
            comp_msg_type = "replan_response" if replan_mode else "staffing_request"
            await self.send_message(
                receiver="compliance_agent",
                message_type=comp_msg_type,
                content=(
                    f"{msg_prefix}Nurse:patient ratio at {effective_ratio:.0%}"
                    f"{' — improved via alternative coverage' if replan_mode else ' — below safe threshold'}. "
                    f"{still_short} positions {'still ' if replan_mode else ''}unresolvable without CMO authorization. "
                    f"{'Updated regulatory exception documentation submitted.' if replan_mode else 'Regulatory exception documentation required.'}"
                ),
                metadata={
                    "effective_ratio": effective_ratio,
                    "still_short": still_short,
                    "requires_cmo": still_short > 0,
                    "ratio_exception_needed": effective_ratio < 0.7,
                    "replan_round": replan_round,
                    "replan_mode": replan_mode,
                    "alternative_coverage_applied": replan_mode,
                },
            )
        elif replan_mode:
            # Replan resolved all issues — notify Compliance
            await self.send_message(
                receiver="compliance_agent",
                message_type="replan_response",
                content=(
                    f"[REPLAN {replan_round}] REVISED PLAN: Staffing fully resolved. "
                    f"Ratio improved to {effective_ratio:.0%} via float pool + extended shifts. "
                    f"No CMO authorization required. All regulatory thresholds met."
                ),
                metadata={
                    "effective_ratio": effective_ratio,
                    "still_short": 0,
                    "requires_cmo": False,
                    "ratio_exception_needed": False,
                    "replan_round": replan_round,
                    "replan_mode": True,
                    "gap_resolved": True,
                    "alternative_coverage_applied": True,
                },
            )

        summary_suffix = (
            f" [REPLAN {replan_round}: float pool +{float_pool_available}, extended shifts +{extended_shift_nurses} applied]"
            if replan_mode else ""
        )
        return {
            "agent_name": self.agent_name,
            "summary": (
                f"Staffing gap of {gap} nurses detected. "
                f"{on_call_available} on-call + {agency_available} agency"
                f"{f' + {float_pool_available} float pool + {extended_shift_nurses} extended shifts' if replan_mode else ''} nurses available. "
                f"{'Escalation required for ' + str(still_short) + ' unresolved positions.' if still_short > 0 else 'Gap can be fully resolved.'}"
                f"{summary_suffix}"
            ),
            "findings": findings,
            "recommendations": recommendations,
            "flags": flags,
            "confidence_score": confidence_score,
            "data": {
                "available_nurses": available_nurses,
                "total_required": total_required,
                "gap": gap,
                "on_call_available": on_call_available,
                "agency_available": agency_available,
                "float_pool_available": float_pool_available,
                "extended_shift_nurses": extended_shift_nurses,
                "still_short": still_short,
                "requires_escalation": still_short > 0,
                "replan_mode": replan_mode,
                "replan_round": replan_round,
                "alternative_coverage_applied": replan_mode,
                "capacity_context_received": bool(capacity_msgs),
            }
        }
