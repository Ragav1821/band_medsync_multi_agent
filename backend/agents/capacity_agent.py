"""
Capacity Agent — Analyzes hospital occupancy, ICU/ED load, and forecasts capacity issues.
Phase 18: Sends capacity_alert to Staffing Agent and occupancy_warning to Resource Agent.
"""
import asyncio
from typing import Dict, List
from agents.base_agent import AgentBase


class CapacityAgent(AgentBase):
    agent_name = "capacity_agent"
    agent_role = "Capacity Analysis Agent"
    agent_description = (
        "Analyzes hospital occupancy, ICU load, ED load, "
        "and forecasts capacity issues with surge projections."
    )

    # Thresholds
    ICU_CRITICAL_THRESHOLD = 85.0
    ICU_SURGE_THRESHOLD = 90.0
    ED_CRITICAL_THRESHOLD = 90.0

    async def analyze(self, incident_data: Dict, inbox: list = None) -> Dict:
        incoming = incident_data.get("incoming_patients", 0)
        icu_pct = incident_data.get("icu_occupancy_pct", 0.0)
        ed_pct = incident_data.get("ed_occupancy_pct", 70.0)
        total_icu_beds = incident_data.get("total_icu_beds", 20)
        available_icu_beds = incident_data.get(
            "available_icu_beds",
            max(0, total_icu_beds - int(total_icu_beds * icu_pct / 100))
        )

        findings = []
        recommendations = []
        flags = []

        # Step 1: Assess current ICU load
        await self._emit_thinking("ICU_ANALYSIS", f"Analyzing ICU occupancy: {icu_pct}% (threshold: {self.ICU_CRITICAL_THRESHOLD}%)")

        if icu_pct >= self.ICU_SURGE_THRESHOLD:
            findings.append(f"ICU occupancy CRITICAL at {icu_pct}% — {available_icu_beds} beds available")
            flags.append("⚠️ CRITICAL: ICU at surge threshold")
        elif icu_pct >= self.ICU_CRITICAL_THRESHOLD:
            findings.append(f"ICU occupancy HIGH at {icu_pct}%")
            flags.append("⚠️ WARNING: ICU approaching capacity")
        else:
            findings.append(f"ICU occupancy stable at {icu_pct}%")

        # Step 2: Assess ED load
        await self._emit_thinking("ED_ANALYSIS", f"Analyzing ED occupancy: {ed_pct}%")
        if ed_pct >= self.ED_CRITICAL_THRESHOLD:
            findings.append(f"ED occupancy CRITICAL at {ed_pct}%")
            flags.append("⚠️ CRITICAL: ED at maximum capacity")
        else:
            findings.append(f"ED occupancy at {ed_pct}%")

        # Step 3: Project capacity with incoming patients
        await self._emit_thinking("SURGE_PROJECTION", f"Projecting capacity for {incoming} incoming patients...")

        projected_icu_pct = icu_pct + (incoming * 0.4)   # 40% of trauma → ICU
        projected_ed_pct  = min(100, ed_pct  + (incoming * 0.8))   # 80% route through ED

        findings.append(f"Projected ICU occupancy with surge: {projected_icu_pct:.1f}%")
        findings.append(f"Projected ED occupancy with surge: {projected_ed_pct:.1f}%")

        if projected_icu_pct > 100:
            flags.append("🚨 CRITICAL: ICU will exceed capacity with incoming patients")

        # Step 4: Surge capacity options
        await self._emit_thinking("SURGE_OPTIONS", "Identifying available surge capacity options...")

        surge_beds_available = 0
        surge_options = []

        if icu_pct > 85:
            transferable = max(0, available_icu_beds + int(total_icu_beds * 0.15))
            surge_options.append(f"Transfer {min(8, transferable)} stable ICU patients to Step-Down Unit")
            surge_beds_available += min(8, transferable)

        if ed_pct > 80:
            surge_options.append("Activate emergency surge protocol: convert conference rooms to overflow beds (+12 beds)")
            surge_beds_available += 12

        if incoming > 30:
            surge_options.append("Activate Hospital Surge Protocol Level 3A immediately")
            surge_options.append("Consider diversion to Regional Medical Center (8 miles)")

        recommendations.extend(surge_options)
        if available_icu_beds < 2 and incoming > 10:
            recommendations.append("Request mutual aid bed availability from neighboring hospitals")

        # Step 5: Time-to-overflow estimate
        await self._emit_thinking("OVERFLOW_ESTIMATE", "Calculating time-to-overflow...")

        if icu_pct > 85 and incoming > 20:
            overflow_hours = max(0.5, (100 - icu_pct) / (incoming * 0.5))
            findings.append(f"Estimated time to ICU overflow: {overflow_hours:.1f} hours without intervention")

        confidence_score = 0.92 if incoming > 0 and icu_pct > 0 else 0.70

        # ── Phase 18: Send messages to peer agents ────────────────────────────
        # Message 1 → Staffing: quantified nursing need from ICU projection
        icu_nurses_needed = max(0, int((projected_icu_pct - 85) / 10) + 2) if projected_icu_pct > 85 else 0
        await self.send_message(
            receiver="staffing_agent",
            message_type="capacity_alert",
            content=(
                f"ICU projected at {projected_icu_pct:.1f}% after incoming surge. "
                f"Estimate {icu_nurses_needed} additional ICU nurses needed immediately. "
                f"Surge capacity: {surge_beds_available} beds identifiable."
            ),
            metadata={
                "projected_icu_pct": projected_icu_pct,
                "projected_ed_pct": projected_ed_pct,
                "icu_nurses_needed": icu_nurses_needed,
                "surge_beds_available": surge_beds_available,
                "overflow_imminent": projected_icu_pct >= 100,
            },
        )

        # Message 2 → Resource: high occupancy signals equipment demand spike
        if projected_icu_pct > 90 or incoming > 20:
            await self.send_message(
                receiver="resource_agent",
                message_type="occupancy_warning",
                content=(
                    f"ICU at {projected_icu_pct:.1f}% with {incoming} incoming patients. "
                    f"Ventilator and critical equipment demand will spike. "
                    f"Prepare mutual aid procurement."
                ),
                metadata={
                    "projected_icu_pct": projected_icu_pct,
                    "incoming_patients": incoming,
                    "critical_equipment_risk": True,
                },
            )

        return {
            "agent_name": self.agent_name,
            "summary": (
                f"ICU at {icu_pct}% (CRITICAL), ED at {ed_pct}%. "
                f"With {incoming} incoming patients, projected ICU load: {projected_icu_pct:.1f}%. "
                f"Surge capacity: {surge_beds_available} additional beds identified."
            ),
            "findings": findings,
            "recommendations": recommendations,
            "flags": flags,
            "confidence_score": confidence_score,
            "data": {
                "current_icu_pct": icu_pct,
                "current_ed_pct": ed_pct,
                "projected_icu_pct": projected_icu_pct,
                "projected_ed_pct": projected_ed_pct,
                "surge_beds_available": surge_beds_available,
                "available_icu_beds": available_icu_beds,
            }
        }
