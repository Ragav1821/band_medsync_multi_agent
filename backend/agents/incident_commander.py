"""
Incident Commander Agent — The master orchestrator.
Coordinates all specialist agents, resolves conflicts, and produces the Final Action Plan.
Phase 19: Integrates ReplanCoordinator for negotiation loop + stores CoordinationRound.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from agents.base_agent import AgentBase
from agents.capacity_agent import CapacityAgent
from agents.staffing_agent import StaffingAgent
from agents.resource_agent import ResourceAgent
from agents.compliance_agent import ComplianceAgent
from agents.replan_coordinator import ReplanCoordinator, CoordinationRound, make_coord_round
from shared.context_store import context_store
from shared.event_bus import emit_escalation, emit_plan_ready, emit_agent_thinking, emit_band_room_created
from shared.agent_messages import message_bus
import services.band_service as band_service

logger = logging.getLogger(__name__)


class IncidentCommanderAgent(AgentBase):
    agent_name = "incident_commander"
    agent_role = "Incident Commander Agent"
    agent_description = (
        "Master orchestrator. Classifies incidents, coordinates specialist agents, "
        "resolves conflicts, validates compliance, and produces the Final Action Plan."
    )

    SEVERITY_THRESHOLDS = {
        "critical": {"incoming": 30, "icu_pct": 85, "label": "LEVEL 3 - CRITICAL"},
        "major":    {"incoming": 10, "icu_pct": 70, "label": "LEVEL 2 - MAJOR"},
        "minor":    {"incoming": 0,  "icu_pct": 0,  "label": "LEVEL 1 - MINOR"},
    }

    def _classify_incident(self, incident_data: Dict) -> tuple[int, str]:
        """Classify incident severity based on incoming data."""
        incoming = incident_data.get("incoming_patients", 0)
        icu_pct = incident_data.get("icu_occupancy_pct", 0.0)
        nurses = incident_data.get("available_nurses", 999)
        vents = incident_data.get("available_ventilators", 999)

        if (incoming >= 30 or icu_pct >= 90 or nurses <= 5 or vents <= 3):
            return 3, "LEVEL 3 - CRITICAL"
        elif (incoming >= 10 or icu_pct >= 70 or nurses <= 15):
            return 2, "LEVEL 2 - MAJOR"
        else:
            return 1, "LEVEL 1 - MINOR"

    async def analyze(self, incident_data: Dict, inbox: list = None) -> Dict:
        """
        Orchestrates the full multi-agent workflow:
        1. Classify incident
        2. Create Band Room
        3. Run 3-round collaborative coordination pipeline (Phase 18)
        4. Phase 19: Run negotiation loop via ReplanCoordinator if REVISION_REQUEST
        5. Synthesize Final Action Plan with CoordinationRound metadata
        6. Post lifecycle messages to Band
        """
        findings = []
        flags = []

        # ── Phase 19: Initialize CoordinationRound ────────────────────────────
        coord_round = make_coord_round(self.incident_id)

        # Phase 1: Classify
        await self._emit_thinking("CLASSIFICATION", "Classifying incident severity level...")
        severity_level, severity_label = self._classify_incident(incident_data)
        findings.append(f"Incident classified as: {severity_label}")

        # Store severity in shared context
        await context_store.set_incident_state(self.incident_id, {
            "severity_level": severity_level,
            "severity_label": severity_label,
            "incident_data": incident_data,
        })

        # ── BAND: Create coordination room ────────────────────────────────────
        incoming = incident_data.get("incoming_patients", 0)
        await self._emit_thinking("BAND_ROOM", "Creating Band coordination room for incident...")
        band_chat_id = await band_service.create_band_room(
            incident_id=self.incident_id,
            title=f"{severity_label} | {incoming} pts incoming",
        )
        if band_chat_id:
            logger.info("[Commander] Band room created: %s", band_chat_id)
            findings.append(f"Band coordination room active: {band_chat_id[:8]}")
            await emit_band_room_created(self.incident_id, band_chat_id)

        # Emit escalation if critical
        if severity_level == 3:
            await emit_escalation(
                self.incident_id,
                "CRITICAL",
                f"Mass casualty event classified {severity_label}. Activating all emergency protocols."
            )
            flags.append("🚨 LEVEL 3 CRITICAL: Executive notification dispatched (CMO, CEO)")

        # ── BAND: Commander dispatches task ───────────────────────────────────
        await band_service.post_agent_message(
            incident_id=self.incident_id,
            sender_agent="incident_commander",
            message_type="DISPATCH",
            content=(
                f"Incident classified: {severity_label}\n"
                f"Incoming patients: {incoming}\n"
                f"ICU occupancy: {incident_data.get('icu_occupancy_pct', 0)}%\n"
                f"Activating Capacity, Staffing, Resource, and Compliance agents."
            ),
            mention_agent="capacity_agent",
        )

        # ── Broadcast initial coordination round state ─────────────────────────
        await self._broadcast_coord_round(coord_round)

        # ──────────────────────────────────────────────────────────────────────
        # PHASE 18: 3-ROUND COLLABORATIVE COORDINATION PIPELINE
        # ──────────────────────────────────────────────────────────────────────

        capacity_agent   = CapacityAgent(self.incident_id)
        staffing_agent   = StaffingAgent(self.incident_id)
        resource_agent   = ResourceAgent(self.incident_id)
        compliance_agent = ComplianceAgent(self.incident_id)

        # ── ROUND 1: Capacity Agent ───────────────────────────────────────────
        await self._emit_thinking(
            "ROUND_1",
            "Coordination Round 1: Capacity Agent analyzing ICU/ED load — "
            "will send peer messages to Staffing and Resource agents."
        )
        capacity_result = await capacity_agent.run(incident_data, inbox=[])
        cap_out = capacity_result.get("output", {})
        coord_round.log_event("ROUND_1_COMPLETE", "Capacity Agent analysis done")

        # ── ROUND 2: Staffing + Resource (consume Capacity messages) ──────────
        await self._emit_thinking(
            "ROUND_2",
            "Coordination Round 2: Staffing and Resource agents reading Capacity "
            "messages and performing cross-informed analysis."
        )
        staffing_inbox = message_bus.get_messages(self.incident_id, receiver="staffing_agent")
        resource_inbox = message_bus.get_messages(self.incident_id, receiver="resource_agent")

        staffing_result, resource_result = await asyncio.gather(
            staffing_agent.run(incident_data, inbox=staffing_inbox),
            resource_agent.run(incident_data, inbox=resource_inbox),
        )
        stf_out = staffing_result.get("output", {})
        res_out = resource_result.get("output", {})
        coord_round.log_event("ROUND_2_COMPLETE", "Staffing + Resource analysis done")

        # ── ROUND 3: Compliance (reads all peer messages) ─────────────────────
        await self._emit_thinking(
            "ROUND_3",
            "Coordination Round 3: Compliance Agent reading all peer messages "
            "from Staffing and Resource agents for regulatory validation."
        )
        compliance_inbox = message_bus.get_messages(self.incident_id, receiver="compliance_agent")
        compliance_result = await compliance_agent.run(incident_data, inbox=compliance_inbox)
        comp_out = compliance_result.get("output", {})
        coord_round.log_event("ROUND_3_COMPLETE", "Compliance initial review done")

        # ── Read Compliance Agent's decision message to Commander ─────────────
        commander_msgs = message_bus.get_messages(self.incident_id, receiver="incident_commander")
        compliance_decision = next(
            (m for m in reversed(commander_msgs)
             if m.sender == "compliance_agent"
             and m.message_type in ("approval", "policy_warning", "rejection", "revision_request")),
            None
        )
        compliance_status_from_msg = compliance_decision.message_type if compliance_decision else "unknown"
        await self._emit_thinking(
            "COMPLIANCE_DECISION",
            f"Compliance Agent verdict received: [{compliance_status_from_msg.upper()}] — "
            f"{compliance_decision.content[:80] + '...' if compliance_decision and len(compliance_decision.content) > 80 else (compliance_decision.content if compliance_decision else 'no message')}."
        )

        # ──────────────────────────────────────────────────────────────────────
        # PHASE 19: NEGOTIATION LOOP — ReplanCoordinator
        # If Compliance issued a REVISION_REQUEST, enter negotiation loop
        # ──────────────────────────────────────────────────────────────────────
        if compliance_status_from_msg == "revision_request":
            await self._emit_thinking(
                "NEGOTIATION_START",
                f"🔄 REVISION REQUEST received from Compliance. "
                f"Activating ReplanCoordinator (max {ReplanCoordinator.MAX_REPLAN_ROUNDS} cycles)."
            )
            coord_round.status = "replanning"
            coord_round.log_event("NEGOTIATION_STARTED", "REVISION_REQUEST detected — entering negotiation loop")
            await self._broadcast_coord_round(coord_round)

            replan_coordinator = ReplanCoordinator(self.incident_id, self)
            compliance_result, coord_round = await replan_coordinator.run_negotiation_loop(
                incident_data=incident_data,
                resource_agent=resource_agent,
                staffing_agent=staffing_agent,
                compliance_agent=compliance_agent,
                initial_compliance_result=compliance_result,
                coord_round=coord_round,
            )
            comp_out = compliance_result.get("output", {})

            # Refresh final compliance decision after negotiation
            commander_msgs = message_bus.get_messages(self.incident_id, receiver="incident_commander")
            compliance_decision = next(
                (m for m in reversed(commander_msgs)
                 if m.sender == "compliance_agent"
                 and m.message_type in ("approval", "policy_warning", "rejection", "revision_request")),
                None
            )
            compliance_status_from_msg = compliance_decision.message_type if compliance_decision else "unknown"

            await self._emit_thinking(
                "NEGOTIATION_COMPLETE",
                f"✅ Negotiation loop complete after {coord_round.replan_count} replan cycle(s). "
                f"Final status: {coord_round.status.upper()}. "
                f"Compliance verdict: {compliance_status_from_msg.upper()}."
            )
        else:
            # No negotiation needed
            if compliance_status_from_msg in ("approval",):
                coord_round.status = "approved"
                coord_round.final_approval_round = coord_round.current_round
            elif compliance_status_from_msg == "policy_warning":
                coord_round.status = "approved"
                coord_round.final_approval_round = coord_round.current_round
                coord_round.log_event("POLICY_WARNING", "Conditionally compliant")
            else:
                coord_round.status = "force_finalized"
                coord_round.final_approval_round = coord_round.current_round

        # ── Broadcast final coordination round state ───────────────────────────
        await self._broadcast_coord_round(coord_round)

        # ── Persist CoordinationRound to SQLite ───────────────────────────────
        try:
            from services.sqlite_service import get_sqlite_service
            get_sqlite_service().save_coordination_round(self.incident_id, coord_round.to_dict())
        except Exception as _se:
            logger.debug("[Commander] SQLite coordination round save failed: %s", _se)

        # ── Log all inter-agent messages to audit trail ────────────────────────
        from services.data_store import store as _store
        all_msgs = message_bus.get_conversation(self.incident_id)
        for msg in all_msgs:
            try:
                audit_evt = msg.to_audit_event()
                _store._log_audit(
                    msg.incident_id,
                    audit_evt["event_type"],
                    audit_evt["actor_type"],
                    audit_evt["actor_id"],
                    audit_evt["event_data"],
                )
            except Exception as _ae:
                logger.debug("[Commander] audit log for message %s failed: %s", msg.id, _ae)

        await self._emit_thinking(
            "MESSAGE_LOG",
            f"Audit trail updated: {len(all_msgs)} inter-agent messages recorded. "
            f"Coordination: {coord_round.current_round} rounds, "
            f"{coord_round.revision_count} revisions, status={coord_round.status}."
        )

        # ── BAND: Each specialist reports findings ────────────────────────────
        await asyncio.gather(
            band_service.post_agent_message(
                incident_id=self.incident_id,
                sender_agent="capacity_agent",
                message_type="REPORT",
                content=cap_out.get("summary", "Analysis complete."),
                mention_agent="incident_commander",
            ),
            band_service.post_agent_message(
                incident_id=self.incident_id,
                sender_agent="staffing_agent",
                message_type="REPORT",
                content=stf_out.get("summary", "Analysis complete."),
                mention_agent="incident_commander",
            ),
            band_service.post_agent_message(
                incident_id=self.incident_id,
                sender_agent="resource_agent",
                message_type="REPORT",
                content=res_out.get("summary", "Analysis complete."),
                mention_agent="incident_commander",
            ),
        )

        await self._emit_thinking("COLLECTION", "Collecting and cross-referencing all specialist outputs + peer messages...")

        # ── BAND: Compliance reports its findings ─────────────────────────────
        await band_service.post_agent_message(
            incident_id=self.incident_id,
            sender_agent="compliance_agent",
            message_type="COMPLIANCE",
            content=(
                f"{comp_out.get('summary', 'Review complete.')}\n"
                f"Status: {comp_out.get('data', {}).get('overall_status', 'UNKNOWN')}\n"
                f"Replan rounds: {coord_round.replan_count}/{ReplanCoordinator.MAX_REPLAN_ROUNDS}"
            ),
            mention_agent="incident_commander",
        )

        # Phase 4: Aggregate all outputs
        all_outputs = {
            "capacity": capacity_result.get("output", {}),
            "staffing": staffing_result.get("output", {}),
            "resource": resource_result.get("output", {}),
            "compliance": compliance_result.get("output", {}),
        }

        # Phase 5: Conflict resolution
        await self._emit_thinking("CONFLICT_RESOLUTION", "Resolving resource conflicts between agents...")

        conflicts = []
        staffing_data = all_outputs["staffing"].get("data", {})
        resource_data = all_outputs["resource"].get("data", {})

        if staffing_data.get("requires_escalation"):
            conflicts.append("Staffing gap cannot be resolved without CMO authorization")
        if resource_data.get("ventilator_gap", 0) > 0:
            conflicts.append("Ventilator shortage requires immediate mutual aid activation")

        # Phase 6: Build action plan
        await self._emit_thinking("ACTION_PLAN", "Synthesizing Final Action Plan from all agent outputs...")

        priority_1 = self._build_priority_1(all_outputs, severity_level)
        priority_2 = self._build_priority_2(all_outputs, severity_level)
        priority_3 = self._build_priority_3(all_outputs)
        escalation_items = self._build_escalation(all_outputs, severity_level, conflicts)

        action_plan_id = str(uuid.uuid4())

        await emit_plan_ready(
            self.incident_id,
            action_plan_id,
            f"Action plan ready: {len(priority_1)} immediate, {len(priority_2)} follow-up, "
            f"{len(escalation_items)} escalations. Negotiation: {coord_round.replan_count} replan(s)."
        )

        # ── BAND: Commander publishes plan ready ──────────────────────────────
        await band_service.post_agent_message(
            incident_id=self.incident_id,
            sender_agent="incident_commander",
            message_type="PLAN_READY",
            content=(
                f"ACTION PLAN SYNTHESIZED — Awaiting human authorization\n"
                f"Immediate actions: {len(priority_1)}\n"
                f"Follow-up actions: {len(priority_2)}\n"
                f"Escalation items: {len(escalation_items)}\n"
                f"Compliance: {all_outputs['compliance'].get('data', {}).get('overall_status', 'UNKNOWN')}\n"
                f"Negotiation rounds: {coord_round.replan_count}/{ReplanCoordinator.MAX_REPLAN_ROUNDS}\n"
                f"Plan ID: {action_plan_id[:8]}"
            ),
            mention_agent="compliance_agent",
        )

        # Collect all flags
        for output in all_outputs.values():
            flags.extend(output.get("flags", []))

        confidence_score = 0.93 if coord_round.replan_count > 0 else 0.91

        # Phase 7: AI Executive Summary
        await self._emit_thinking(
            "EXECUTIVE_SUMMARY",
            "Synthesizing Executive Summary via Gemini AI..."
        )
        executive_summary = await self._synthesize_executive_summary(
            incident_data=incident_data,
            severity_level=severity_level,
            severity_label=severity_label,
            all_outputs=all_outputs,
            priority_1=priority_1,
            priority_2=priority_2,
            escalation_items=escalation_items,
            conflicts=conflicts,
            flags=flags,
        )

        replan_note = (
            f" After {coord_round.replan_count} negotiation cycle(s), "
            f"Compliance issued final {coord_round.status.upper()} verdict."
            if coord_round.replan_count > 0 else ""
        )

        return {
            "agent_name": self.agent_name,
            "summary": (
                f"Incident classified {severity_label}. "
                f"All 4 specialist agents coordinated. "
                f"Final Action Plan: {len(priority_1)} immediate actions, "
                f"{len(priority_2)} follow-ups, {len(escalation_items)} escalations."
                f"{replan_note}"
            ),
            "findings": findings + conflicts,
            "recommendations": priority_1 + priority_2,
            "flags": flags,
            "confidence_score": confidence_score,
            "executive_summary": executive_summary,
            "action_plan": {
                "id": action_plan_id,
                "severity_level": severity_level,
                "severity_label": severity_label,
                "priority_1_actions": priority_1,
                "priority_2_actions": priority_2,
                "priority_3_actions": priority_3,
                "escalation_items": escalation_items,
                "compliance_status": all_outputs["compliance"].get("data", {}).get("overall_status", "UNKNOWN"),
                "required_documentation": all_outputs["compliance"].get("data", {}).get("required_documentation", []),
                "agent_outputs": all_outputs,
                # Phase 19: embed coordination round metadata in action plan
                "coordination_round": coord_round.to_dict(),
            }
        }

    # ── Phase 19: WebSocket broadcast helper ──────────────────────────────────

    async def _broadcast_coord_round(self, coord_round: CoordinationRound) -> None:
        """Broadcast coordination round state update to all WebSocket clients."""
        from shared.event_bus import ws_manager
        try:
            await ws_manager.broadcast_to_incident(self.incident_id, {
                "event_type": "negotiation:round_update",
                "incident_id": self.incident_id,
                "coordination_round": coord_round.to_dict(),
            })
        except Exception as exc:
            logger.debug("[Commander] coord round broadcast failed: %s", exc)

    # ------------------------------------------------------------------
    # Phase 7: Executive Summary Synthesis
    # ------------------------------------------------------------------
    async def _synthesize_executive_summary(
        self,
        incident_data: Dict,
        severity_level: int,
        severity_label: str,
        all_outputs: Dict,
        priority_1: List[Dict],
        priority_2: List[Dict],
        escalation_items: List[str],
        conflicts: List[str],
        flags: List[str],
    ) -> Dict:
        fallback = self._deterministic_executive_summary(
            incident_data=incident_data,
            severity_level=severity_level,
            severity_label=severity_label,
            all_outputs=all_outputs,
            priority_1=priority_1,
            priority_2=priority_2,
            escalation_items=escalation_items,
            conflicts=conflicts,
            flags=flags,
        )

        prompt = self._build_gemini_prompt(
            incident_data=incident_data,
            severity_label=severity_label,
            all_outputs=all_outputs,
            priority_1=priority_1,
            priority_2=priority_2,
            escalation_items=escalation_items,
            conflicts=conflicts,
        )

        system_instruction = (
            "You are the Chief Medical Officer AI assistant for a hospital emergency command center. "
            "Your role is to synthesize multi-agent analysis into a concise, actionable executive summary "
            "for hospital leadership. Be precise, clinical, and prioritise patient safety. "
            "Always respond with valid JSON only — no markdown, no prose outside the JSON object."
        )

        try:
            result = await self._call_llm(
                prompt=prompt,
                system_instruction=system_instruction,
                fallback=fallback,
                temperature=0.2,
            )
            if not all(k in result for k in ("executive_summary", "critical_risks", "action_plan")):
                logger.warning(
                    "[incident_commander] Gemini response missing required keys → deterministic fallback"
                )
                return fallback

            result["ai_generated"] = not result.get("simulation_mode", False)
            return result

        except Exception as exc:
            logger.error(
                "[incident_commander] _synthesize_executive_summary error → fallback. %s", exc
            )
            return fallback

    @staticmethod
    def _build_gemini_prompt(
        incident_data: Dict,
        severity_label: str,
        all_outputs: Dict,
        priority_1: List[Dict],
        priority_2: List[Dict],
        escalation_items: List[str],
        conflicts: List[str],
    ) -> str:
        cap  = all_outputs.get("capacity", {})
        stf  = all_outputs.get("staffing", {})
        res  = all_outputs.get("resource", {})
        comp = all_outputs.get("compliance", {})

        cap_summary  = cap.get("summary", "N/A")
        stf_summary  = stf.get("summary", "N/A")
        res_summary  = res.get("summary", "N/A")
        comp_summary = comp.get("summary", "N/A")

        cap_findings  = "\n".join(f"  - {f}" for f in cap.get("findings", []))
        stf_findings  = "\n".join(f"  - {f}" for f in stf.get("findings", []))
        res_findings  = "\n".join(f"  - {f}" for f in res.get("findings", []))
        comp_findings = "\n".join(f"  - {f}" for f in comp.get("findings", []))

        p1_list = "\n".join(
            f"  - [{a.get('timeline','?')}] {a.get('description','?')} → {a.get('responsible_party','?')}"
            for a in priority_1
        )
        p2_list = "\n".join(
            f"  - [{a.get('timeline','?')}] {a.get('description','?')} → {a.get('responsible_party','?')}"
            for a in priority_2
        )
        escalation_list = "\n".join(f"  - {e}" for e in escalation_items)
        conflict_list   = "\n".join(f"  - {c}" for c in conflicts) or "  None"

        return f"""You are synthesizing a hospital emergency executive summary.

INCIDENT SEVERITY: {severity_label}
INCOMING PATIENTS: {incident_data.get('incoming_patients', 0)}
ICU OCCUPANCY: {incident_data.get('icu_occupancy_pct', 0)}%
ED OCCUPANCY: {incident_data.get('ed_occupancy_pct', 0)}%

=== CAPACITY AGENT ===
Summary: {cap_summary}
Findings:
{cap_findings or '  None'}

=== STAFFING AGENT ===
Summary: {stf_summary}
Findings:
{stf_findings or '  None'}

=== RESOURCE AGENT ===
Summary: {res_summary}
Findings:
{res_findings or '  None'}

=== COMPLIANCE AGENT ===
Summary: {comp_summary}
Findings:
{comp_findings or '  None'}

=== IMMEDIATE ACTIONS (Priority 1) ===
{p1_list or '  None'}

=== FOLLOW-UP ACTIONS (Priority 2) ===
{p2_list or '  None'}

=== ESCALATION ITEMS ===
{escalation_list or '  None'}

=== RESOURCE CONFLICTS ===
{conflict_list}

Based on the above multi-agent analysis, generate a JSON object with EXACTLY this structure:
{{
  "executive_summary": "<2-3 sentence board-level narrative summarising the situation and response>",
  "critical_risks": [
    "<risk 1>",
    "<risk 2>",
    "<risk 3>"
  ],
  "action_plan": [
    {{"priority": 1, "action": "<action>", "owner": "<owner>", "eta": "<eta>"}},
    {{"priority": 2, "action": "<action>", "owner": "<owner>", "eta": "<eta>"}}
  ]
}}

Rules:
- executive_summary must be concise (max 3 sentences), clinical, and suitable for C-suite briefing.
- critical_risks: list exactly the top 3 patient-safety or operational risks.
- action_plan: include only the top 5 most impactful actions ordered by priority.
- Respond with JSON ONLY. No markdown. No extra text."""

    def _deterministic_executive_summary(
        self,
        incident_data: Dict,
        severity_level: int,
        severity_label: str,
        all_outputs: Dict,
        priority_1: List[Dict],
        priority_2: List[Dict],
        escalation_items: List[str],
        conflicts: List[str],
        flags: List[str],
    ) -> Dict:
        incoming   = incident_data.get("incoming_patients", 0)
        icu_pct    = incident_data.get("icu_occupancy_pct", 0.0)
        ed_pct     = incident_data.get("ed_occupancy_pct", 0.0)
        cap_data   = all_outputs.get("capacity", {}).get("data", {})
        stf_data   = all_outputs.get("staffing", {}).get("data", {})
        res_data   = all_outputs.get("resource", {}).get("data", {})
        comp_data  = all_outputs.get("compliance", {}).get("data", {})

        severity_phrase = {
            3: "a LEVEL 3 CRITICAL mass casualty event",
            2: "a LEVEL 2 MAJOR surge event",
            1: "a LEVEL 1 MINOR operational event",
        }.get(severity_level, "an emergency event")

        exec_summary = (
            f"The hospital is responding to {severity_phrase} with {incoming} incoming patients, "
            f"ICU occupancy at {icu_pct}%, and ED occupancy at {ed_pct}%. "
        )
        if conflicts:
            exec_summary += f"Active resource conflicts have been identified: {conflicts[0]}. "
        exec_summary += (
            f"All 4 specialist agents have been coordinated and a Final Action Plan with "
            f"{len(priority_1)} immediate and {len(priority_2)} follow-up actions has been generated."
        )

        critical_risks: List[str] = []
        if cap_data.get("projected_icu_pct", 0) > 90:
            critical_risks.append(
                f"ICU projected to reach {cap_data['projected_icu_pct']:.0f}% — overflow risk within hours"
            )
        if res_data.get("ventilator_gap", 0) > 0:
            critical_risks.append(
                f"Ventilator shortage: {res_data['ventilator_gap']} units deficit — mutual aid required immediately"
            )
        if stf_data.get("still_short", 0) > 0:
            critical_risks.append(
                f"Staffing gap of {stf_data['still_short']} nurses unresolvable without CMO authorization"
            )
        if res_data.get("blood_gap", 0) > 0:
            critical_risks.append(
                f"Blood supply deficit: {res_data['blood_gap']} units below safe threshold"
            )
        if comp_data.get("overall_status") == "REQUIRES_REVIEW":
            critical_risks.append("Compliance review required before executing certain protocols")
        critical_risks = critical_risks[:3] or ["Monitor ICU utilisation every 15 minutes"]

        combined_actions = [
            {
                "priority": idx + 1,
                "action": a.get("description", ""),
                "owner": a.get("responsible_party", "Operations"),
                "eta": a.get("timeline", "ASAP"),
            }
            for idx, a in enumerate((priority_1 + priority_2)[:5])
        ]

        return {
            "executive_summary": exec_summary,
            "critical_risks": critical_risks,
            "action_plan": combined_actions,
            "ai_generated": False,
            "simulation_mode": True,
        }

    def _build_priority_1(self, outputs: Dict, severity: int) -> List[Dict]:
        actions = []
        cap = outputs["capacity"]
        res = outputs["resource"]

        if severity >= 3:
            actions.append({
                "id": str(uuid.uuid4())[:8],
                "description": "Activate Hospital Surge Protocol Level 3A immediately",
                "responsible_party": "Hospital Operations Manager",
                "timeline": "Immediate (0–2 min)",
                "is_compliant": True,
            })

        if cap.get("data", {}).get("projected_icu_pct", 0) > 100:
            actions.append({
                "id": str(uuid.uuid4())[:8],
                "description": "Begin transfer of 8 stable ICU patients to Step-Down Unit",
                "responsible_party": "ICU Administrator",
                "timeline": "Immediate (0–5 min)",
                "is_compliant": True,
            })

        if res.get("data", {}).get("ventilator_gap", 0) > 0:
            actions.append({
                "id": str(uuid.uuid4())[:8],
                "description": "Activate mutual aid: contact City General Hospital for ventilator transfer",
                "responsible_party": "Resource Manager",
                "timeline": "Immediate (0–5 min)",
                "is_compliant": True,
            })

        return actions

    def _build_priority_2(self, outputs: Dict, severity: int) -> List[Dict]:
        actions = []
        staff = outputs["staffing"]
        res = outputs["resource"]

        on_call = staff.get("data", {}).get("on_call_available", 0)
        if on_call > 0:
            actions.append({
                "id": str(uuid.uuid4())[:8],
                "description": f"Authorize and activate {on_call} on-call nurses (30-min ETA)",
                "responsible_party": "Nursing Supervisor",
                "timeline": "15 minutes",
                "is_compliant": True,
            })

        agency = staff.get("data", {}).get("agency_available", 0)
        if agency > 0:
            actions.append({
                "id": str(uuid.uuid4())[:8],
                "description": f"Request {agency} agency nurses from registered staffing pool",
                "responsible_party": "Nursing Supervisor",
                "timeline": "15 minutes",
                "is_compliant": True,
            })

        if res.get("data", {}).get("blood_gap", 0) > 0:
            actions.append({
                "id": str(uuid.uuid4())[:8],
                "description": "Contact regional blood center for emergency supply + initiate hospital blood drive",
                "responsible_party": "Lab / Blood Bank Manager",
                "timeline": "30 minutes",
                "is_compliant": True,
            })

        actions.append({
            "id": str(uuid.uuid4())[:8],
            "description": "Reallocate 2 ventilators from elective surgery floor to emergency use",
            "responsible_party": "Resource Manager",
            "timeline": "15 minutes",
            "is_compliant": True,
        })

        return actions

    def _build_priority_3(self, outputs: Dict) -> List[Dict]:
        compliance_data = outputs["compliance"].get("data", {})
        required_docs = compliance_data.get("required_documentation", [])

        actions = []
        for doc in required_docs:
            actions.append({
                "id": str(uuid.uuid4())[:8],
                "description": f"Complete: {doc}",
                "responsible_party": "Compliance / Operations",
                "timeline": "1 hour",
                "is_compliant": True,
            })

        return actions

    def _build_escalation(self, outputs: Dict, severity: int, conflicts: List[str]) -> List[str]:
        escalations = []

        if severity >= 3:
            escalations.append("NOTIFY CMO: Level 3 Critical event — staffing authorization required")
            escalations.append("NOTIFY CEO/Hospital Leadership: Mass casualty event active")
            escalations.append("NOTIFY State Health Department: Surge protocol activated (within 1 hour)")

        staff_data = outputs["staffing"].get("data", {})
        if staff_data.get("still_short", 0) > 0:
            escalations.append(
                f"EXECUTIVE DECISION REQUIRED: {staff_data['still_short']} nurses unresolvable without CMO authorization"
            )

        comp_data = outputs["compliance"].get("data", {})
        if comp_data.get("overall_status") in ("REQUIRES_REVIEW",):
            escalations.append("LEGAL/COMPLIANCE TEAM: Compliance review required before proceeding")

        return escalations
