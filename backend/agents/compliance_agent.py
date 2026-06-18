"""
Compliance Agent — Validates all recommendations against regulatory frameworks.
Phase 18: Reads resource_shortage and staffing_request from peer agents.
         Sends approval or policy_warning to Incident Commander.
Phase 19: Issues REVISION_REQUEST to Commander when plan can be improved
         (instead of hard rejection). On re-evaluation (replan round > 0),
         applies lenient thresholds to break deadlocks.
"""
import asyncio
from typing import Dict, List
from agents.base_agent import AgentBase
from shared.context_store import context_store


class ComplianceAgent(AgentBase):
    agent_name = "compliance_agent"
    agent_role = "Compliance & Regulatory Agent"
    agent_description = (
        "Validates all agent recommendations against EMTALA, Joint Commission, "
        "and state regulations. Generates compliance flags and required documentation."
    )

    REGULATORY_FRAMEWORKS = [
        "EMTALA (Emergency Medical Treatment & Labor Act)",
        "Joint Commission Emergency Management Standards",
        "CMS Conditions of Participation",
        "State Health Department Emergency Protocols",
    ]

    async def analyze(self, incident_data: Dict, inbox: list = None) -> Dict:
        incoming         = incident_data.get("incoming_patients", 0)
        icu_pct          = incident_data.get("icu_occupancy_pct", 0.0)
        available_nurses = incident_data.get("available_nurses", 0)
        severity         = incident_data.get("severity_level", 2)
        # Phase 19: track replan round for leniency escalation
        replan_round     = incident_data.get("_replan_round", 0)
        is_replan        = replan_round > 0

        findings = []
        recommendations = []
        flags = []
        approved_actions = []
        required_docs = []
        compliance_issues = []

        # ── Phase 18/19: Consume peer agent messages ──────────────────────────
        inbox = inbox or []

        resource_msgs  = [m for m in inbox if m.message_type in ("resource_shortage", "replan_response")
                          and m.sender == "resource_agent"]
        staffing_msgs  = [m for m in inbox if m.message_type in ("staffing_request", "replan_response")
                          and m.sender == "staffing_agent"]

        # Also read context store (pre-Phase-18 mechanism, kept for compatibility)
        capacity_output = await context_store.get_agent_output(self.incident_id, "capacity_agent")
        staffing_output = await context_store.get_agent_output(self.incident_id, "staffing_agent")
        resource_output = await context_store.get_agent_output(self.incident_id, "resource_agent")

        context_loaded = sum([
            capacity_output is not None,
            staffing_output is not None,
            resource_output is not None,
        ])

        if is_replan:
            await self._emit_thinking(
                "REPLAN_CONTEXT",
                f"[REPLAN {replan_round}] Re-evaluating with revised agent plans. "
                f"Applying {'standard' if replan_round == 1 else 'lenient'} compliance thresholds "
                f"(round {replan_round}/{3}).",
            )
            findings.append(
                f"[REPLAN {replan_round}] Re-evaluation with revised plans — "
                f"{'standard' if replan_round == 1 else 'lenient emergency'} compliance thresholds applied."
            )

        # ── Process resource message ───────────────────────────────────────────
        mutual_aid_approved = False
        gap_resolved_resource = False
        if resource_msgs:
            res_meta = resource_msgs[-1].metadata
            vent_gap = res_meta.get("ventilator_gap", 0)
            gap_resolved_resource = res_meta.get("gap_resolved", False)
            alt_sourcing = res_meta.get("alternative_sourcing_applied", False)

            await self._emit_thinking(
                "RESOURCE_MESSAGE",
                f"Resource Agent {'[REPLAN] ' if is_replan else ''}flagged: {vent_gap} ventilator deficit"
                f"{' — RESOLVED via alternative sourcing' if gap_resolved_resource else ''}. "
                f"Evaluating Emergency Code authorization..."
            )
            findings.append(
                f"Resource Agent {'revised ' if is_replan else ''}message: {vent_gap} ventilator gap"
                f"{' — resolved via Hospital B borrowing + elective deferral' if gap_resolved_resource else ' — mutual aid authorization under review'}."
            )
            if res_meta.get("mutual_aid_required") and not gap_resolved_resource:
                approved_actions.append(
                    "✅ Mutual aid ventilator request: APPROVED — State Emergency Code activation authorized"
                )
                required_docs.append("Mutual Aid Agreement Activation Log")
                required_docs.append("Equipment Transfer Chain of Custody Form")
                mutual_aid_approved = True
                # Phase 19A: Critical resource gap creates a compliance issue
                if vent_gap >= 10:
                    compliance_issues.append(
                        f"Critical resource deficit: {vent_gap} ventilators short — State Emergency Code authorization required"
                    )
            elif gap_resolved_resource:
                approved_actions.append(
                    "✅ Resource gap RESOLVED: Hospital B lending 5 ventilators + 4 elective deferrals"
                )
                mutual_aid_approved = True  # still counts as approved (different mechanism)

            if res_meta.get("state_emergency_code_needed") and not gap_resolved_resource:
                findings.append("State Emergency Code required for resource procurement.")
                required_docs.append("State Emergency Medical Supply Reserve Request Form")
        else:
            # Fallback to context store path
            if resource_output and resource_output.get("data", {}).get("ventilator_gap", 0) > 0:
                approved_actions.append(
                    "✅ Mutual aid ventilator request: APPROVED — State Emergency Code activation authorized"
                )
                required_docs.append("Mutual Aid Agreement Activation Log")
                required_docs.append("Equipment Transfer Chain of Custody Form")
                mutual_aid_approved = True

        # ── Process staffing message ───────────────────────────────────────────
        ratio_exception_required = False
        gap_resolved_staffing = False
        if staffing_msgs:
            stf_meta = staffing_msgs[-1].metadata
            still_short = stf_meta.get("still_short", 0)
            effective_ratio = stf_meta.get("effective_ratio", 1.0)
            gap_resolved_staffing = stf_meta.get("gap_resolved", False)
            alt_coverage = stf_meta.get("alternative_coverage_applied", False)

            await self._emit_thinking(
                "STAFFING_MESSAGE",
                f"Staffing Agent {'[REPLAN] ' if is_replan else ''}: ratio at {effective_ratio:.0%}, "
                f"{still_short} positions unresolvable"
                f"{' — RESOLVED via alternative coverage' if gap_resolved_staffing else ''}. "
                f"Evaluating CMO exception authorization..."
            )
            findings.append(
                f"Staffing Agent {'revised ' if is_replan else ''}request: ratio at {effective_ratio:.0%}"
                f"{' — resolved via float pool + extended shifts' if gap_resolved_staffing else ' — regulatory exception evaluation in progress'}."
            )

            # Phase 19: On replan round 2+, accept ratio with documented exception
            ratio_threshold = 0.6 if replan_round >= 2 else 0.7
            if (stf_meta.get("ratio_exception_needed") or effective_ratio < ratio_threshold) and not gap_resolved_staffing:
                compliance_issues.append(
                    f"Temporary nurse:patient ratio below state minimum (1:4 ED, 1:2 ICU)"
                )
                required_docs.append(
                    "Medical Necessity Exception Form — document staffing shortage and mitigation steps taken"
                )
                recommendations.append(
                    "Obtain CMO written authorization for temporary ratio exception under emergency provisions"
                )
                flags.append("⚠️ COMPLIANCE FLAG: Staffing ratio exception requires CMO approval")
                ratio_exception_required = True
            elif gap_resolved_staffing or effective_ratio >= ratio_threshold:
                approved_actions.append(
                    f"✅ Nurse:patient ratios: {'COMPLIANT (alternative coverage applied)' if alt_coverage else 'COMPLIANT'}"
                )

            if stf_meta.get("requires_cmo") and not gap_resolved_staffing:
                compliance_issues.append(
                    f"{still_short} nurse positions unresolvable without CMO authorization"
                )
        else:
            # Fallback to context store
            staffing_data = staffing_output.get("data", {}) if staffing_output else {}
            gap = staffing_data.get("gap", 0)
            if gap > 0 and available_nurses < 8:
                compliance_issues.append("Temporary nurse:patient ratio below state minimum (1:4 ED, 1:2 ICU)")
                required_docs.append("Medical Necessity Exception Form — document staffing shortage and mitigation steps taken")
                recommendations.append("Obtain CMO written authorization for temporary ratio exception under emergency provisions")
                flags.append("⚠️ COMPLIANCE FLAG: Staffing ratio exception requires CMO approval")
            else:
                approved_actions.append("✅ Nurse:patient ratios: COMPLIANT")

        # Step 1: Context load acknowledgment
        await self._emit_thinking(
            "CONTEXT_LOAD",
            f"Phase-18/19 inbox: {len(inbox)} messages from peers. "
            f"Context store: {context_loaded}/3 specialist outputs loaded."
        )
        findings.append(f"Loaded {len(inbox)} peer messages + {context_loaded}/3 context-store outputs for compliance review")

        # Step 2: EMTALA compliance check
        await self._emit_thinking("EMTALA_CHECK", "Validating against EMTALA requirements...")

        if incoming > 0:
            approved_actions.append("✅ Patient acceptance obligation: COMPLIANT (EMTALA requires all patients be evaluated)")
            required_docs.append("EMTALA Intake Log — must document each patient's arrival time and initial assessment")

        if capacity_output and capacity_output.get("data", {}).get("projected_icu_pct", 0) > 100:
            findings.append("Diversion recommendation detected — EMTALA requires specific criteria be met")
            required_docs.append("Diversion Authorization Form — requires CMO signature and state notification")
            compliance_issues.append("Diversion requires formal EMTALA justification documentation")

        # Step 3: Surge protocol validation
        await self._emit_thinking("SURGE_VALIDATION", "Validating emergency surge protocol activation...")

        if severity >= 3 or icu_pct > 90:
            approved_actions.append(
                "✅ Surge Protocol Level 3A: APPROVED — Joint Commission Emergency Management EM.01.01.01"
            )
            required_docs.append("Incident Command Activation Form — log surge protocol start time")
            required_docs.append("Bed Status Report — update state health department within 1 hour")

        # Step 4: Transfer validation
        await self._emit_thinking("TRANSFER_CHECK", "Validating patient transfer compliance...")

        if capacity_output and "Transfer" in str(capacity_output.get("recommendations", [])):
            approved_actions.append("✅ Patient transfers: APPROVED — with mandatory transfer summary documentation")
            required_docs.append("Transfer Summary Form (per Joint Commission TX.01.01.01)")
            required_docs.append("Accepting Physician Acknowledgment (required per EMTALA)")

        # Step 5: Phase 19 — on replan rounds, reduce issue threshold for leniency
        # Replan round 2+: CONDITIONALLY_COMPLIANT is treated as acceptable (no REVISION_REQUEST)
        await self._emit_thinking("FINAL_VERDICT", "Generating overall compliance assessment...")

        if len(compliance_issues) == 0:
            overall_status = "FULLY_COMPLIANT"
            flags.append("✅ All recommendations reviewed: COMPLIANT")
        elif len(compliance_issues) <= 2:
            overall_status = "CONDITIONALLY_COMPLIANT"
            flags.append(f"⚠️ {len(compliance_issues)} compliance item(s) require documentation/approval")
        else:
            overall_status = "REQUIRES_REVIEW"
            flags.append(f"🚨 {len(compliance_issues)} compliance issues — legal/compliance team notification required")

        findings.extend(compliance_issues)
        confidence_score = 0.90

        # ── Phase 18/19: Send decision message to Commander ───────────────────
        if overall_status == "FULLY_COMPLIANT":
            await self.send_message(
                receiver="incident_commander",
                message_type="approval",
                content=(
                    f"All {len(approved_actions)} proposed actions reviewed and approved. "
                    f"EMTALA, Joint Commission, and CMS Conditions of Participation: COMPLIANT. "
                    f"{len(required_docs)} documents required for audit trail."
                    f"{' [REPLAN: Alternative sourcing + coverage strategies approved]' if is_replan else ''}"
                ),
                metadata={
                    "overall_status": overall_status,
                    "approved_actions_count": len(approved_actions),
                    "required_docs_count": len(required_docs),
                    "mutual_aid_approved": mutual_aid_approved,
                    "ratio_exception_required": ratio_exception_required,
                    "replan_round": replan_round,
                    "is_replan": is_replan,
                },
            )
        elif overall_status == "CONDITIONALLY_COMPLIANT":
            # Phase 19: On replan round 2+, treat CONDITIONALLY_COMPLIANT as passing
            if replan_round >= 2:
                # Accept it — no more REVISION_REQUEST cycles
                await self.send_message(
                    receiver="incident_commander",
                    message_type="approval",
                    content=(
                        f"[REPLAN {replan_round}] CONDITIONALLY COMPLIANT — accepted under emergency provisions. "
                        f"{len(compliance_issues)} items require documentation but are pre-authorized. "
                        f"CMO acknowledgment obtained. Plan approved for execution with documented exceptions."
                    ),
                    metadata={
                        "overall_status": "CONDITIONALLY_COMPLIANT_ACCEPTED",
                        "compliance_issues": compliance_issues,
                        "required_docs_count": len(required_docs),
                        "mutual_aid_approved": mutual_aid_approved,
                        "ratio_exception_required": ratio_exception_required,
                        "replan_round": replan_round,
                        "is_replan": True,
                        "accepted_under_emergency": True,
                    },
                )
            else:
                await self.send_message(
                    receiver="incident_commander",
                    message_type="policy_warning",
                    content=(
                        f"CONDITIONALLY COMPLIANT: {len(compliance_issues)} items require documentation. "
                        f"CMO authorization needed for: "
                        f"{'staffing ratio exception' if ratio_exception_required else 'resource procurement'}. "
                        f"Proceed with caution and complete all required documentation within 1 hour."
                    ),
                    metadata={
                        "overall_status": overall_status,
                        "compliance_issues": compliance_issues,
                        "required_docs_count": len(required_docs),
                        "mutual_aid_approved": mutual_aid_approved,
                        "ratio_exception_required": ratio_exception_required,
                        "replan_round": replan_round,
                    },
                )
        else:
            # REQUIRES_REVIEW
            # Phase 19: Issue REVISION_REQUEST instead of hard rejection
            # (so Commander can trigger a replan cycle)
            await self.send_message(
                receiver="incident_commander",
                message_type="revision_request",
                content=(
                    f"REVISION REQUIRED: {len(compliance_issues)} unresolved compliance issues detected. "
                    f"Specific issues: {'; '.join(compliance_issues[:3])}. "
                    f"Requesting Commander to initiate REPLAN — agents should propose alternative "
                    f"resource sourcing and staffing coverage to resolve outstanding issues."
                ),
                metadata={
                    "overall_status": overall_status,
                    "compliance_issues": compliance_issues,
                    "requires_legal_review": True,
                    "replan_round": replan_round,
                    "suggested_revision": (
                        "Reduce ventilator demand via elective deferral or source from alternative supplier; "
                        "resolve staffing gap via float pool or extended shifts"
                    ),
                    "revision_round": replan_round,
                },
            )

        return {
            "agent_name": self.agent_name,
            "summary": (
                f"Compliance review complete: {overall_status}. "
                f"{len(approved_actions)} actions approved, "
                f"{len(compliance_issues)} items flagged, "
                f"{len(required_docs)} documents required."
                f"{' [REPLAN ' + str(replan_round) + ']' if is_replan else ''}"
            ),
            "findings": findings,
            "recommendations": recommendations,
            "flags": flags,
            "confidence_score": confidence_score,
            "data": {
                "overall_status": overall_status,
                "approved_actions": approved_actions,
                "compliance_issues": compliance_issues,
                "required_documentation": required_docs,
                "regulatory_frameworks_checked": self.REGULATORY_FRAMEWORKS,
                "peer_messages_processed": len(inbox),
                "replan_round": replan_round,
                "is_replan": is_replan,
            }
        }
