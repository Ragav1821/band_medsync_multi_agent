"""
Compliance Agent — Validates all recommendations against regulatory frameworks.
Reads other agents' outputs from the shared context store before analyzing.
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

    async def analyze(self, incident_data: Dict) -> Dict:
        incoming = incident_data.get("incoming_patients", 0)
        icu_pct = incident_data.get("icu_occupancy_pct", 0.0)
        available_nurses = incident_data.get("available_nurses", 0)
        severity = incident_data.get("severity_level", 2)

        findings = []
        recommendations = []
        flags = []
        approved_actions = []
        required_docs = []
        compliance_issues = []

        # Step 1: Read other agents' outputs from shared context
        await self._emit_thinking(
            "CONTEXT_LOAD",
            "Loading specialist agent outputs for validation review..."
        )
        
        capacity_output = await context_store.get_agent_output(self.incident_id, "capacity_agent")
        staffing_output = await context_store.get_agent_output(self.incident_id, "staffing_agent")
        resource_output = await context_store.get_agent_output(self.incident_id, "resource_agent")

        context_loaded = sum([
            capacity_output is not None,
            staffing_output is not None,
            resource_output is not None,
        ])
        findings.append(f"Loaded outputs from {context_loaded}/3 specialist agents for compliance review")

        # Step 2: EMTALA compliance check
        await self._emit_thinking("EMTALA_CHECK", "Validating against EMTALA requirements...")
        
        if incoming > 0:
            approved_actions.append("✅ Patient acceptance obligation: COMPLIANT (EMTALA requires all patients be evaluated)")
            required_docs.append("EMTALA Intake Log — must document each patient's arrival time and initial assessment")
        
        # If capacity agent recommended diversion
        if capacity_output and capacity_output.get("data", {}).get("projected_icu_pct", 0) > 100:
            findings.append("Diversion recommendation detected — EMTALA requires specific criteria be met")
            required_docs.append("Diversion Authorization Form — requires CMO signature and state notification")
            compliance_issues.append("Diversion requires formal EMTALA justification documentation")

        # Step 3: Nurse ratio compliance
        await self._emit_thinking("RATIO_COMPLIANCE", "Checking nurse-patient ratio regulations...")
        
        staffing_data = staffing_output.get("data", {}) if staffing_output else {}
        gap = staffing_data.get("gap", 0)
        
        if gap > 0 and available_nurses < 8:
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
        else:
            approved_actions.append("✅ Nurse:patient ratios: COMPLIANT")

        # Step 4: Surge protocol validation
        await self._emit_thinking("SURGE_VALIDATION", "Validating emergency surge protocol activation...")
        
        if severity >= 3 or icu_pct > 90:
            approved_actions.append(
                "✅ Surge Protocol Level 3A: APPROVED — Joint Commission Emergency Management EM.01.01.01"
            )
            required_docs.append("Incident Command Activation Form — log surge protocol start time")
            required_docs.append("Bed Status Report — update state health department within 1 hour")
        
        # Step 5: Transfer validation
        await self._emit_thinking("TRANSFER_CHECK", "Validating patient transfer compliance...")
        
        if capacity_output and "Transfer" in str(capacity_output.get("recommendations", [])):
            approved_actions.append(
                "✅ Patient transfers: APPROVED — with mandatory transfer summary documentation"
            )
            required_docs.append("Transfer Summary Form (per Joint Commission TX.01.01.01)")
            required_docs.append("Accepting Physician Acknowledgment (required per EMTALA)")

        # Step 6: Mutual aid validation
        await self._emit_thinking("MUTUAL_AID", "Validating mutual aid resource requests...")
        
        if resource_output and resource_output.get("data", {}).get("ventilator_gap", 0) > 0:
            approved_actions.append(
                "✅ Mutual aid ventilator request: APPROVED — State Emergency Code activation authorized"
            )
            required_docs.append("Mutual Aid Agreement Activation Log")
            required_docs.append("Equipment Transfer Chain of Custody Form")

        # Step 7: Generate overall compliance status
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

        return {
            "agent_name": self.agent_name,
            "summary": (
                f"Compliance review complete: {overall_status}. "
                f"{len(approved_actions)} actions approved, "
                f"{len(compliance_issues)} items flagged, "
                f"{len(required_docs)} documents required."
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
            }
        }
