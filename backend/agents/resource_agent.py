"""
Resource Agent — Monitors medical resources, equipment, and emergency inventory.
Phase 18: Reads occupancy_warning from Capacity and staffing_gap from Staffing.
         Sends resource_shortage to Compliance Agent.
Phase 19: Handles REPLAN_REQUEST from Commander — proposes alternative sourcing
         strategies and sends REPLAN_RESPONSE back to Compliance.
Phase 20: Loop B: Always sends RESOURCE_CONSTRAINT back to Staffing (workstation cap).
         Loop C: Reads COMPLIANCE_POLICY_OBJECTION and sends ALTERNATIVE_PLAN to Compliance.
"""
import asyncio
from typing import Dict, List
from agents.base_agent import AgentBase


class ResourceAgent(AgentBase):
    agent_name = "resource_agent"
    agent_role = "Resource Management Agent"
    agent_description = (
        "Monitors critical medical resources, detects shortages, "
        "calculates time-to-depletion, and recommends procurement actions."
    )

    VENTILATOR_CRITICAL = 5
    BLOOD_BANK_CRITICAL = 20

    async def analyze(self, incident_data: Dict, inbox: list = None) -> Dict:
        incoming   = incident_data.get("incoming_patients", 0)
        ventilators = incident_data.get("available_ventilators", 0)
        blood_units = incident_data.get("blood_bank_units", 50)
        severity    = incident_data.get("severity_level", 2)

        findings = []
        recommendations = []
        flags = []

        # ── Phase 18: Consume peer messages ─────────────────────────────────────
        inbox = inbox or []

        capacity_msgs = [m for m in inbox if m.message_type == "occupancy_warning"]
        staffing_msgs = [m for m in inbox if m.message_type == "staffing_gap"
                         or m.message_type == "staffing_feasibility_response"]

        # ── Phase 19: Detect REPLAN_REQUEST from Commander ───────────────────
        replan_msgs  = [m for m in inbox if m.message_type == "replan_request"]
        replan_mode  = bool(replan_msgs)
        replan_round = replan_msgs[-1].metadata.get("replan_round", 0) if replan_msgs else 0

        # ── Phase 20 Loop C: Detect COMPLIANCE_POLICY_OBJECTION ────────────────
        # Compliance sends this to challenge a transfer plan violating EMTALA
        policy_objection_msgs = [m for m in inbox if m.message_type == "compliance_policy_objection"]
        policy_objection = policy_objection_msgs[-1] if policy_objection_msgs else None
        if policy_objection:
            await self._emit_thinking(
                "POLICY_OBJECTION_RECEIVED",
                f"⇦ Compliance challenged our plan: {policy_objection.content[:100]}. "
                f"Generating alternative sourcing strategy that avoids EMTALA conflict."
            )
            findings.append(
                f"Compliance policy objection received: {policy_objection.metadata.get('policy_ref', 'EMTALA §1395dd')} — "
                f"revising to Hospital B MOU borrowing to avoid prohibited patient transfer."
            )

        icu_beds_to_equip = 0
        incoming_boosted  = incoming

        if capacity_msgs:
            cap_meta = capacity_msgs[-1].metadata
            projected_icu = cap_meta.get("projected_icu_pct", 0)
            incoming_boosted = cap_meta.get("incoming_patients", incoming)
            await self._emit_thinking(
                "CAPACITY_INPUT",
                f"Capacity Agent: ICU projected at {projected_icu:.1f}%. "
                f"Adjusting ventilator demand estimate upward."
            )
            findings.append(
                f"Capacity Agent alert received: ICU surge to {projected_icu:.1f}% — "
                f"recalibrating equipment demand."
            )

        if staffing_msgs:
            stf_meta = staffing_msgs[-1].metadata
            icu_beds_to_equip = stf_meta.get("icu_beds_to_equip", stf_meta.get("nurses_coverable", 0))
            await self._emit_thinking(
                "STAFFING_INPUT",
                f"Staffing Agent: {icu_beds_to_equip} ICU positions need equipment support. "
                f"Prioritising ventilator allocation to those positions."
            )
            findings.append(
                f"Staffing Agent request: ensure equipment for {icu_beds_to_equip} ICU nurse positions."
            )

        if replan_mode:
            await self._emit_thinking(
                "REPLAN_MODE",
                f"[REPLAN ROUND {replan_round}] Commander requests revised resource allocation. "
                f"Evaluating alternative sourcing: Hospital B borrowing, "
                f"elective deferral, emergency vendor activation.",
            )
            findings.append(
                f"[REPLAN {replan_round}] Commander requested resource revision — "
                f"applying alternative sourcing strategies."
            )
            recommendations.insert(0, "Borrow 5 ventilators from Hospital B (MOU active, 20-min transfer ETA)")
            recommendations.insert(1, "Defer 4 non-critical elective procedures — free up 4 ventilators immediately")

        # Step 1: Ventilator analysis
        await self._emit_thinking("VENTILATOR_CHECK", f"Analyzing ventilator inventory: {ventilators} available...")

        # Phase 19: In replan mode use lower demand multiplier (alternative allocation reduces net gap)
        if replan_mode:
            vent_multiplier = 0.18   # reduced via reallocation + borrowed units
        else:
            vent_multiplier = 0.30 if capacity_msgs else (0.25 if severity >= 3 else 0.10)

        vent_demand = max(1, int(incoming_boosted * vent_multiplier))
        vent_demand = max(vent_demand, icu_beds_to_equip)   # at least what Staffing needs
        # In replan mode, treat borrowed ventilators as available
        effective_ventilators = ventilators + (5 if replan_mode else 0)
        vent_gap = max(0, vent_demand - effective_ventilators)

        findings.append(f"Available ventilators: {ventilators}" + (f" (+5 borrowed from Hospital B)" if replan_mode else ""))
        findings.append(f"Estimated demand for {incoming} patients (severity {severity}): {vent_demand} ventilators")

        if ventilators < self.VENTILATOR_CRITICAL:
            flags.append(f"🚨 CRITICAL: Only {ventilators} ventilators available — below safety threshold of {self.VENTILATOR_CRITICAL}")

        if vent_gap > 0:
            findings.append(f"VENTILATOR SHORTAGE: {vent_gap} unit(s) deficit")
            flags.append(f"⚠️ CRITICAL: Ventilator gap of {vent_gap} units")
        elif replan_mode:
            findings.append(f"[REPLAN] Ventilator gap RESOLVED via Hospital B borrowing + elective deferral.")

        # Step 2: Ventilator procurement
        await self._emit_thinking("PROCUREMENT", "Evaluating ventilator procurement options...")

        if vent_gap > 0:
            recommendations.append(
                f"Contact City General Hospital mutual aid: {min(vent_gap, 7)} ventilators available (30-min transfer)"
            )

        if incoming > 20:
            recommendations.append("Reallocate 2 ventilators from elective surgery floor (non-critical patients)")

        if vent_gap > 3:
            recommendations.append("Activate state emergency medical supply reserve — submit request immediately")
            recommendations.append("Emergency vendor delivery: contact MedEquip Solutions for priority shipment (ETA: 3 hours)")

        # Step 3: Blood bank
        await self._emit_thinking("BLOOD_BANK", f"Checking blood bank levels: {blood_units} units...")

        blood_demand = int(incoming * 1.5) if severity >= 3 else int(incoming * 0.5)
        blood_gap    = max(0, blood_demand - blood_units)

        findings.append(f"Blood bank inventory: {blood_units} units")
        findings.append(f"Estimated blood demand for surge: {blood_demand} units")

        if blood_gap > 0:
            flags.append(f"⚠️ WARNING: Blood bank may be insufficient — {blood_gap} unit shortfall projected")
            recommendations.append(
                f"Request emergency blood donation drive + contact regional blood center for {blood_gap} units"
            )

        # Step 4: Additional supplies
        await self._emit_thinking("SUPPLIES_CHECK", "Reviewing critical supplies inventory...")

        if incoming > 30:
            findings.append("High incoming volume: PPE and surgical supply consumption will accelerate")
            recommendations.append("Activate emergency supply reorder protocol for PPE, IV supplies, and surgical kits")

        if severity == 3 and incoming > 40:
            recommendations.append("Establish emergency supply staging area in Parking Structure B")
            flags.append("⚠️ WARNING: Supply chain stress expected within 4-6 hours at current consumption rate")

        # Step 5: Time to depletion
        await self._emit_thinking("DEPLETION_EST", "Estimating time-to-depletion for critical resources...")

        if ventilators > 0 and vent_demand > 0:
            hours_to_vent_depletion = (effective_ventilators / vent_demand) * 2
            findings.append(f"Estimated ventilator depletion: {hours_to_vent_depletion:.1f} hours at current demand")

        confidence_score = 0.87 if replan_mode else 0.85

        # ── Phase 18/19/20: Send messages to peer agents ──────────────────────

        # Phase 20 Loop B: ALWAYS send RESOURCE_CONSTRAINT back to Staffing.
        # This creates the bidirectional Staffing ↔ Resource channel regardless of replan state.
        # ICU workstation cap: assume 1.2 workstations per ventilator available.
        max_icu_nurses_supported = max(1, int(effective_ventilators * 1.2) + 4)
        await self.send_message(
            receiver="staffing_agent",
            message_type="resource_constraint",
            content=(
                f"Physical ICU capacity constraint: {effective_ventilators} ventilators + monitoring stations "
                f"support a maximum of {max_icu_nurses_supported} ICU nurses simultaneously. "
                f"{'Ventilator shortage of ' + str(vent_gap) + ' units — coordinate with mutual aid.' if vent_gap > 0 else 'Equipment available for current nurse deployment.'}"
            ),
            metadata={
                "max_icu_nurses": max_icu_nurses_supported,
                "ventilators_available": effective_ventilators,
                "ventilator_gap": vent_gap,
                "equipment_ready": vent_gap == 0,
                "replan_mode": replan_mode,
            },
        )

        # Phase 20 Loop C: If Compliance issued a policy objection, respond with ALTERNATIVE_PLAN.
        if policy_objection:
            await self.send_message(
                receiver="compliance_agent",
                message_type="alternative_plan",
                content=(
                    f"Alternative sourcing plan (avoids EMTALA patient transfer conflict): "
                    f"Hospital B MOU lending {min(vent_gap + 2, 7)} ventilators (MOU ref: HB-2024-EMRG, 20-min ETA). "
                    f"Elective surgery deferrals free 4 additional units. "
                    f"No patient transfer required — EMTALA §1395dd conflict resolved. "
                    f"Net ventilator deficit after alternative sourcing: 0 units."
                ),
                metadata={
                    "plan_type": "alternative_sourcing",
                    "emtala_conflict_resolved": True,
                    "hospital_b_units": min(vent_gap + 2, 7),
                    "elective_deferrals": 4,
                    "net_vent_gap": 0,
                    "policy_ref": policy_objection.metadata.get("policy_ref", "EMTALA §1395dd"),
                    "objection_resolved": True,
                },
            )
            findings.append(
                "Alternative plan submitted to Compliance: Hospital B MOU borrowing replaces prohibited transfer. "
                "EMTALA objection resolved."
            )
        if vent_gap > 0 or blood_gap > 10:
            shortage_summary_parts = []
            if vent_gap > 0:
                shortage_summary_parts.append(f"{vent_gap} ventilator deficit")
            if blood_gap > 10:
                shortage_summary_parts.append(f"{blood_gap} blood unit shortfall")

            # Phase 19: In replan mode, send REPLAN_RESPONSE (revised plan)
            msg_type = "replan_response" if replan_mode else "resource_shortage"
            msg_prefix = f"[REPLAN {replan_round}] REVISED PLAN: " if replan_mode else ""

            await self.send_message(
                receiver="compliance_agent",
                message_type=msg_type,
                content=(
                    f"{msg_prefix}Resource shortage update: {', '.join(shortage_summary_parts)}. "
                    f"{'Alternative sourcing applied: Hospital B borrowing + elective deferral. ' if replan_mode else ''}"
                    f"{'Revised mutual aid request — reduced scope. ' if replan_mode else 'Mutual aid activation required. '}"
                    f"State Emergency Code authorization and equipment chain-of-custody documentation needed."
                ),
                metadata={
                    "ventilator_gap": vent_gap,
                    "ventilators_available": effective_ventilators,
                    "ventilators_needed": vent_demand,
                    "blood_gap": blood_gap,
                    "mutual_aid_required": vent_gap > 0,
                    "state_emergency_code_needed": vent_gap > 3,
                    "replan_round": replan_round,
                    "replan_mode": replan_mode,
                    "alternative_sourcing_applied": replan_mode,
                },
            )
        elif replan_mode and vent_gap == 0:
            # Replan resolved the gap — send approval-ready response
            await self.send_message(
                receiver="compliance_agent",
                message_type="replan_response",
                content=(
                    f"[REPLAN {replan_round}] REVISED PLAN: Ventilator gap RESOLVED. "
                    f"Hospital B lending 5 units (MOU ref: HB-2024-EMRG). "
                    f"4 elective surgeries deferred. Net shortfall: 0 units. "
                    f"Blood bank within safe limits. Mutual aid scope reduced."
                ),
                metadata={
                    "ventilator_gap": 0,
                    "ventilators_available": effective_ventilators,
                    "ventilators_needed": vent_demand,
                    "blood_gap": blood_gap,
                    "mutual_aid_required": False,
                    "state_emergency_code_needed": False,
                    "replan_round": replan_round,
                    "replan_mode": True,
                    "gap_resolved": True,
                    "alternative_sourcing_applied": True,
                },
            )

        # Message → Commander if supply chain stress is extreme (only on initial run)
        if not replan_mode and severity == 3 and (vent_gap > 5 or blood_gap > 50):
            await self.send_message(
                receiver="incident_commander",
                message_type="equipment_constraint",
                content=(
                    f"EXTREME resource constraint: ventilator gap {vent_gap}, blood deficit {blood_gap} units. "
                    f"Recommend immediate CMO/CEO notification and multi-hospital mutual aid network activation."
                ),
                metadata={
                    "ventilator_gap": vent_gap,
                    "blood_gap": blood_gap,
                    "executive_notification_required": True,
                },
            )

        summary_suffix = (
            f" [REPLAN {replan_round}: Hospital B +5 vents, 4 elective deferrals applied]"
            if replan_mode else ""
        )
        return {
            "agent_name": self.agent_name,
            "summary": (
                f"Ventilator shortage: {vent_gap} units deficit (have {effective_ventilators}, need {vent_demand}). "
                f"Blood bank: {blood_units} units vs {blood_demand} projected demand. "
                f"{'Alternative sourcing applied.' if replan_mode else 'Mutual aid and procurement options identified.'}"
                f"{summary_suffix}"
            ),
            "findings": findings,
            "recommendations": recommendations,
            "flags": flags,
            "confidence_score": confidence_score,
            "data": {
                "ventilators_available": effective_ventilators,
                "ventilators_needed": vent_demand,
                "ventilator_gap": vent_gap,
                "blood_units_available": blood_units,
                "blood_demand": blood_demand,
                "blood_gap": blood_gap,
                "critical_shortage": vent_gap > 0 or blood_gap > 10,
                "replan_mode": replan_mode,
                "replan_round": replan_round,
                "alternative_sourcing_applied": replan_mode,
                "peer_context_received": {
                    "from_capacity": bool(capacity_msgs),
                    "from_staffing": bool(staffing_msgs),
                    "from_commander_replan": replan_mode,
                },
            }
        }
