"""
ReplanCoordinator — Phase 19 (P1 + P4)
Negotiation loop engine: detects REVISION_REQUEST from Compliance,
issues REPLAN_REQUEST to Resource + Staffing, re-runs Compliance,
and loops up to MAX_REPLAN_ROUNDS times before force-finalising.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agents.incident_commander import IncidentCommanderAgent
    from agents.resource_agent import ResourceAgent
    from agents.staffing_agent import StaffingAgent
    from agents.compliance_agent import ComplianceAgent

from shared.agent_messages import message_bus, AgentMessage, MessageType
from shared.event_bus import (
    emit_agent_message,
    emit_agent_thinking,
    emit_negotiation_revision_requested,
    emit_negotiation_replanning_started,
    emit_negotiation_reapproved,
    emit_negotiation_completed,
)

logger = logging.getLogger(__name__)


# ── Coordination Round Model ───────────────────────────────────────────────────

@dataclass
class CoordinationRound:
    incident_id: str
    current_round: int = 1
    max_rounds: int = 3
    revision_count: int = 0
    replan_count: int = 0
    status: str = "initial"              # initial | replanning | approved | rejected | force_finalized
    final_approval_round: Optional[int] = None
    negotiation_log: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    def log_event(self, event: str, detail: str = ""):
        self.negotiation_log.append({
            "round": self.current_round,
            "event": event,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# ── ReplanCoordinator ──────────────────────────────────────────────────────────

class ReplanCoordinator:
    """
    Orchestrates the negotiation loop between Compliance and the specialist agents.

    Flow per revision cycle:
      1. Detect REVISION_REQUEST in commander inbox
      2. Emit REPLAN_REQUEST from Commander → Resource + Staffing
      3. Re-run Resource + Staffing agents with REPLAN_REQUEST in their inbox
      4. Re-run Compliance with the revised messages
      5. If REVISION_REQUEST again AND rounds remain → loop
      6. If max rounds exhausted → force-finalise (accept CONDITIONALLY_COMPLIANT)
    """

    MAX_REPLAN_ROUNDS = 3

    def __init__(self, incident_id: str, commander: "IncidentCommanderAgent"):
        self.incident_id = incident_id
        self.commander = commander

    # ── Public entry point ─────────────────────────────────────────────────────

    async def run_negotiation_loop(
        self,
        incident_data: Dict,
        resource_agent: "ResourceAgent",
        staffing_agent: "StaffingAgent",
        compliance_agent: "ComplianceAgent",
        initial_compliance_result: Dict,
        coord_round: CoordinationRound,
    ) -> tuple[Dict, CoordinationRound]:
        """
        Inspect initial compliance result; if REVISION_REQUEST is present,
        run replan cycles until approval or max rounds exhausted.

        Returns (final_compliance_result, updated_coord_round).
        """
        compliance_result = initial_compliance_result

        while coord_round.replan_count < self.MAX_REPLAN_ROUNDS:
            # Check if Compliance issued a REVISION_REQUEST to Commander
            revision_msg = self._find_latest_revision_request(coord_round.current_round)
            if revision_msg is None:
                # No revision request — loop complete
                logger.info(
                    "[ReplanCoordinator] Round %d: no REVISION_REQUEST found — finalising.",
                    coord_round.current_round,
                )
                break

            coord_round.revision_count += 1
            coord_round.replan_count += 1
            coord_round.current_round += 1
            coord_round.status = "replanning"
            coord_round.log_event(
                "REVISION_REQUESTED",
                revision_msg.content[:120],
            )

            logger.info(
                "[ReplanCoordinator] REVISION_REQUEST detected. Starting replan %d/%d.",
                coord_round.replan_count, self.MAX_REPLAN_ROUNDS,
            )

            # Phase 19A: Emit granular negotiation event
            replan_issues = revision_msg.metadata.get("compliance_issues", [])
            await emit_negotiation_revision_requested(
                self.incident_id, replan_issues, coord_round.current_round
            )

            # ── Step 1: Commander issues REPLAN_REQUEST ────────────────────────
            replan_content = (
                f"REPLAN ROUND {coord_round.replan_count}: Compliance requires revision. "
                f"Issues: {'; '.join(replan_issues[:3])}. "
                f"Please propose alternative allocation strategies."
            )

            await self._emit_step(
                "NEGOTIATION_REPLAN",
                f"[Replan {coord_round.replan_count}/{self.MAX_REPLAN_ROUNDS}] "
                f"Compliance issued REVISION_REQUEST. "
                f"Commander dispatching REPLAN_REQUEST to Resource + Staffing agents.",
            )

            # Commander sends REPLAN_REQUEST to both agents
            replan_msg_resource = await self.commander.send_message(
                receiver="resource_agent",
                message_type="replan_request",
                content=replan_content,
                metadata={
                    "replan_round": coord_round.replan_count,
                    "compliance_issues": replan_issues,
                    "suggested_strategy": "source_alternative",
                },
            )
            replan_msg_staffing = await self.commander.send_message(
                receiver="staffing_agent",
                message_type="replan_request",
                content=replan_content,
                metadata={
                    "replan_round": coord_round.replan_count,
                    "compliance_issues": replan_issues,
                    "suggested_strategy": "alternative_shifts",
                },
            )
            coord_round.log_event("REPLAN_REQUEST_ISSUED", f"Round {coord_round.replan_count}")

            # Phase 19A: Emit replanning started event
            await emit_negotiation_replanning_started(
                self.incident_id, coord_round.replan_count, self.MAX_REPLAN_ROUNDS
            )

            # ── Step 2: Re-run Resource + Staffing with REPLAN_REQUEST in inbox ─
            await self._emit_step(
                "NEGOTIATION_AGENTS_REVISING",
                f"Resource and Staffing agents revising plans (replan {coord_round.replan_count})...",
            )

            resource_inbox = message_bus.get_messages(
                self.incident_id, receiver="resource_agent"
            )
            staffing_inbox = message_bus.get_messages(
                self.incident_id, receiver="staffing_agent"
            )

            from agents.resource_agent import ResourceAgent as _RA
            from agents.staffing_agent import StaffingAgent as _SA

            new_resource_agent = _RA(self.incident_id)
            new_staffing_agent = _SA(self.incident_id)

            revised_resource_result, revised_staffing_result = await asyncio.gather(
                new_resource_agent.run(incident_data, inbox=resource_inbox),
                new_staffing_agent.run(incident_data, inbox=staffing_inbox),
            )

            coord_round.log_event(
                "AGENTS_REVISED",
                f"Resource + Staffing submitted revised plans for replan {coord_round.replan_count}",
            )

            # ── Step 3: Re-run Compliance with all updated messages ────────────
            await self._emit_step(
                "NEGOTIATION_COMPLIANCE_RECHECK",
                f"Compliance Agent re-evaluating revised plans (replan {coord_round.replan_count})...",
            )

            compliance_inbox = message_bus.get_messages(
                self.incident_id, receiver="compliance_agent"
            )

            # Mark replan round in incident_data so Compliance applies correct leniency
            revised_incident_data = {
                **incident_data,
                "_replan_round": coord_round.replan_count,
            }

            from agents.compliance_agent import ComplianceAgent as _CA
            new_compliance_agent = _CA(self.incident_id)
            compliance_result = await new_compliance_agent.run(
                revised_incident_data, inbox=compliance_inbox
            )

            coord_round.log_event(
                "COMPLIANCE_RECHECKED",
                compliance_result.get("output", {}).get("summary", "")[:120],
            )

            # ── Step 4: Check the new compliance decision ──────────────────────
            new_decision = self._find_latest_revision_request(coord_round.current_round)
            compliance_status = compliance_result.get("output", {}).get(
                "data", {}
            ).get("overall_status", "UNKNOWN")

            if new_decision is None:
                # Compliance approved (no new REVISION_REQUEST) → exit loop
                coord_round.status = "approved"
                coord_round.final_approval_round = coord_round.current_round
                coord_round.log_event("APPROVED", f"Compliance approved on round {coord_round.current_round}")
                await self._emit_step(
                    "NEGOTIATION_APPROVED",
                    f"✅ Compliance APPROVED revised plan on replan round {coord_round.replan_count}.",
                )
                # Phase 19A: Emit reapproved + completed events
                await emit_negotiation_reapproved(
                    self.incident_id, coord_round.current_round, "approved"
                )
                await emit_negotiation_completed(
                    self.incident_id, "approved", coord_round.current_round, coord_round.replan_count
                )
                break

        else:
            # Max replan rounds exhausted — force-finalise
            await self._force_finalize(coord_round, compliance_agent, incident_data)
            compliance_result_final = message_bus.get_messages(
                self.incident_id, receiver="incident_commander"
            )
            # Use the last compliance result available
            logger.warning(
                "[ReplanCoordinator] Max replan rounds exhausted. Force-finalising."
            )
            # Phase 19A: Emit completed event for force-finalization
            await emit_negotiation_completed(
                self.incident_id, "force_finalized", coord_round.current_round, coord_round.replan_count
            )

        # If never set to approved/force_finalized above, check final status
        if coord_round.status == "replanning":
            final_status = compliance_result.get("output", {}).get(
                "data", {}
            ).get("overall_status", "UNKNOWN")
            if final_status in ("FULLY_COMPLIANT", "CONDITIONALLY_COMPLIANT"):
                coord_round.status = "approved"
                coord_round.final_approval_round = coord_round.current_round
            else:
                coord_round.status = "force_finalized"
                coord_round.final_approval_round = coord_round.current_round

        return compliance_result, coord_round

    # ── Private helpers ────────────────────────────────────────────────────────

    def _find_latest_revision_request(self, current_round: int) -> Optional[AgentMessage]:
        """Look for the most recent REVISION_REQUEST sent to Commander."""
        msgs = message_bus.get_messages(
            self.incident_id,
            receiver="incident_commander",
        )
        # Find messages that are revision_requests from compliance
        for msg in reversed(msgs):
            if (
                msg.message_type == MessageType.REVISION_REQUEST
                and msg.sender == "compliance_agent"
                # Only pick up ones that don't already have a replan_ack
                and not msg.metadata.get("acked")
            ):
                # Mark acked so we don't reprocess
                msg.metadata["acked"] = True
                return msg
        return None

    async def _force_finalize(
        self,
        coord_round: CoordinationRound,
        compliance_agent: "ComplianceAgent",
        incident_data: Dict,
    ) -> None:
        """Issue a FORCE_FINAL thinking step and accept whatever Compliance returns."""
        coord_round.status = "force_finalized"
        coord_round.final_approval_round = coord_round.current_round
        coord_round.log_event(
            "FORCE_FINALIZED",
            f"Max replan rounds ({self.MAX_REPLAN_ROUNDS}) exhausted. Accepting best available plan.",
        )
        await self._emit_step(
            "NEGOTIATION_FORCE_FINAL",
            f"⚠️ Max replan cycles ({self.MAX_REPLAN_ROUNDS}) reached. "
            "Force-finalising with best available compliance assessment.",
        )
        # Send a final compliance message acknowledging forced finalization
        await self.commander.send_message(
            receiver="all",
            message_type="escalation",
            content=(
                f"FORCE FINAL: After {self.MAX_REPLAN_ROUNDS} replan cycles, "
                "plan is finalised with outstanding compliance notes. "
                "CMO review required before execution."
            ),
            metadata={
                "force_finalized": True,
                "replan_cycles_used": self.MAX_REPLAN_ROUNDS,
            },
        )

    async def _emit_step(self, step: str, content: str) -> None:
        """Emit an agent:thinking event from the commander's perspective."""
        from shared.event_bus import emit_agent_thinking
        await emit_agent_thinking(self.incident_id, "incident_commander", step, content)
        await asyncio.sleep(0.2)


# ── Factory ────────────────────────────────────────────────────────────────────

def make_coord_round(incident_id: str) -> CoordinationRound:
    """Create a fresh CoordinationRound for a new incident."""
    return CoordinationRound(incident_id=incident_id)
