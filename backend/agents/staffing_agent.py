"""
Staffing Agent — Monitors staff availability, detects shortages, recommends staffing actions.
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
    ICU_RATIO = 1       # 1 nurse per 1-2 ICU patients
    ED_RATIO = 1        # 1 nurse per 3-4 ED patients
    GENERAL_RATIO = 1   # 1 nurse per 4-6 general patients

    async def analyze(self, incident_data: Dict) -> Dict:
        incoming = incident_data.get("incoming_patients", 0)
        available_nurses = incident_data.get("available_nurses", 0)
        icu_pct = incident_data.get("icu_occupancy_pct", 0.0)
        total_icu_beds = incident_data.get("total_icu_beds", 20)

        findings = []
        recommendations = []
        flags = []

        # Step 1: Calculate required staffing
        await self._emit_thinking("STAFFING_CALC", "Calculating required nurse staffing for surge scenario...")
        
        icu_patients = int(total_icu_beds * icu_pct / 100)
        ed_patients_est = int(incoming * 0.8)
        
        required_icu_nurses = max(1, icu_patients // 2)
        required_ed_nurses = max(1, ed_patients_est // 3)
        required_general_nurses = max(1, (incoming - ed_patients_est) // 4)
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
        
        on_call_available = min(gap, 6) if gap > 0 else 0  # Simulated on-call pool
        agency_available = min(max(0, gap - on_call_available), 8)  # Agency pool
        still_short = max(0, gap - on_call_available - agency_available)

        if on_call_available > 0:
            recommendations.append(
                f"Activate {on_call_available} on-call nurses immediately (30-min ETA)"
            )
        if agency_available > 0:
            recommendations.append(
                f"Request {agency_available} agency nurses from registered staffing pool (60-min ETA)"
            )
        if still_short > 0:
            recommendations.append(
                f"Authorize mandatory overtime for {still_short} additional nurses — requires CMO approval"
            )
            flags.append(f"🚨 ESCALATION: {still_short} nurses unresolvable without executive authorization")

        # Step 4: Shift allocation
        await self._emit_thinking("ALLOCATION", "Calculating optimal nurse allocation by unit...")
        
        recommendations.append(
            f"Allocate {required_icu_nurses} nurses to ICU (priority: ventilated patients)"
        )
        recommendations.append(
            f"Allocate {min(available_nurses, required_ed_nurses)} nurses to ED triage"
        )

        # Step 5: Ratio compliance check
        await self._emit_thinking("RATIO_CHECK", "Verifying nurse-patient ratios against safe care standards...")
        
        effective_ratio = available_nurses / max(1, total_required)
        if effective_ratio < 0.7:
            flags.append("⚠️ WARNING: Nurse:patient ratio below safe thresholds until on-call staff arrives")
            recommendations.append(
                "Document temporary ratio exception with medical necessity justification"
            )

        confidence_score = 0.88

        return {
            "agent_name": self.agent_name,
            "summary": (
                f"Staffing gap of {gap} nurses detected. "
                f"{on_call_available} on-call + {agency_available} agency nurses available. "
                f"{'Escalation required for ' + str(still_short) + ' unresolved positions.' if still_short > 0 else 'Gap can be fully resolved.'}"
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
                "still_short": still_short,
                "requires_escalation": still_short > 0,
            }
        }
