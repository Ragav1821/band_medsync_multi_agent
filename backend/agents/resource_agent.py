"""
Resource Agent — Monitors medical resources, equipment, and emergency inventory.
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

    async def analyze(self, incident_data: Dict) -> Dict:
        incoming = incident_data.get("incoming_patients", 0)
        ventilators = incident_data.get("available_ventilators", 0)
        blood_units = incident_data.get("blood_bank_units", 50)
        severity = incident_data.get("severity_level", 2)

        findings = []
        recommendations = []
        flags = []

        # Step 1: Ventilator analysis
        await self._emit_thinking("VENTILATOR_CHECK", f"Analyzing ventilator inventory: {ventilators} available...")
        
        # Estimate ventilator demand (20-30% of critical trauma patients need vents)
        vent_demand = max(1, int(incoming * 0.25)) if severity >= 3 else max(1, int(incoming * 0.10))
        vent_gap = max(0, vent_demand - ventilators)
        
        findings.append(f"Available ventilators: {ventilators}")
        findings.append(f"Estimated demand for {incoming} patients (severity {severity}): {vent_demand} ventilators")
        
        if ventilators < self.VENTILATOR_CRITICAL:
            flags.append(f"🚨 CRITICAL: Only {ventilators} ventilators available — below safety threshold of {self.VENTILATOR_CRITICAL}")
        
        if vent_gap > 0:
            findings.append(f"VENTILATOR SHORTAGE: {vent_gap} unit(s) deficit")
            flags.append(f"⚠️ CRITICAL: Ventilator gap of {vent_gap} units")

        # Step 2: Ventilator procurement options
        await self._emit_thinking("PROCUREMENT", "Evaluating ventilator procurement options...")
        
        if vent_gap > 0:
            recommendations.append(
                f"Contact City General Hospital mutual aid: {min(vent_gap, 7)} ventilators available (30-min transfer)"
            )
        
        # Internal reallocation
        if incoming > 20:
            recommendations.append(
                "Reallocate 2 ventilators from elective surgery floor (non-critical patients)"
            )
        
        if vent_gap > 3:
            recommendations.append(
                "Activate state emergency medical supply reserve — submit request immediately"
            )
            recommendations.append(
                "Emergency vendor delivery: contact MedEquip Solutions for priority shipment (ETA: 3 hours)"
            )

        # Step 3: Blood bank analysis
        await self._emit_thinking("BLOOD_BANK", f"Checking blood bank levels: {blood_units} units...")
        
        blood_demand = int(incoming * 1.5) if severity >= 3 else int(incoming * 0.5)
        blood_gap = max(0, blood_demand - blood_units)
        
        findings.append(f"Blood bank inventory: {blood_units} units")
        findings.append(f"Estimated blood demand for surge: {blood_demand} units")
        
        if blood_gap > 0:
            flags.append(f"⚠️ WARNING: Blood bank may be insufficient — {blood_gap} unit shortfall projected")
            recommendations.append(
                f"Request emergency blood donation drive + contact regional blood center for {blood_gap} units"
            )

        # Step 4: Additional critical supplies
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
            hours_to_vent_depletion = (ventilators / vent_demand) * 2
            findings.append(f"Estimated ventilator depletion: {hours_to_vent_depletion:.1f} hours at current demand")

        confidence_score = 0.85

        return {
            "agent_name": self.agent_name,
            "summary": (
                f"Ventilator shortage: {vent_gap} units deficit (have {ventilators}, need {vent_demand}). "
                f"Blood bank: {blood_units} units vs {blood_demand} projected demand. "
                f"Mutual aid and procurement options identified."
            ),
            "findings": findings,
            "recommendations": recommendations,
            "flags": flags,
            "confidence_score": confidence_score,
            "data": {
                "ventilators_available": ventilators,
                "ventilators_needed": vent_demand,
                "ventilator_gap": vent_gap,
                "blood_units_available": blood_units,
                "blood_demand": blood_demand,
                "blood_gap": blood_gap,
                "critical_shortage": vent_gap > 0 or blood_gap > 10,
            }
        }
