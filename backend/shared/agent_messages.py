"""
Agent Message Model & In-Memory Message Bus
Phase 18 — True Collaborative Multi-Agent System

Agents send structured typed messages to each other through this bus.
The Commander orchestrates multi-round coordination loops.
Every message is also written to the audit trail and broadcast over WebSocket.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Message Type Registry ──────────────────────────────────────────────────────

class MessageType(str, Enum):
    # Capacity Agent → others
    CAPACITY_ALERT       = "capacity_alert"
    OCCUPANCY_WARNING    = "occupancy_warning"

    # Staffing Agent → others
    STAFFING_GAP         = "staffing_gap"
    STAFFING_REQUEST     = "staffing_request"

    # Resource Agent → others
    RESOURCE_SHORTAGE    = "resource_shortage"
    EQUIPMENT_CONSTRAINT = "equipment_constraint"

    # Compliance Agent → others
    APPROVAL             = "approval"
    REJECTION            = "rejection"
    POLICY_WARNING       = "policy_warning"

    # Incident Commander → others
    ASSIGNMENT           = "assignment"
    ESCALATION           = "escalation"
    CLARIFICATION_REQUEST = "clarification_request"

    # Phase 19 — Negotiation Loop
    REVISION_REQUEST     = "revision_request"   # Compliance → Commander: reject + ask for replan
    REPLAN_REQUEST       = "replan_request"     # Commander → Resource/Staffing: try again
    REPLAN_RESPONSE      = "replan_response"    # Resource/Staffing → Compliance: revised plan


# ── Communication Contracts ─────────────────────────────────────────────────────
# Defines which message types each agent is allowed to send.
AGENT_CONTRACTS: Dict[str, List[str]] = {
    "capacity_agent":    [MessageType.CAPACITY_ALERT, MessageType.OCCUPANCY_WARNING],
    "staffing_agent":    [MessageType.STAFFING_GAP, MessageType.STAFFING_REQUEST, MessageType.REPLAN_RESPONSE],
    "resource_agent":    [MessageType.RESOURCE_SHORTAGE, MessageType.EQUIPMENT_CONSTRAINT, MessageType.REPLAN_RESPONSE],
    "compliance_agent":  [MessageType.APPROVAL, MessageType.REJECTION, MessageType.POLICY_WARNING, MessageType.REVISION_REQUEST],
    "incident_commander": [MessageType.ASSIGNMENT, MessageType.ESCALATION, MessageType.CLARIFICATION_REQUEST, MessageType.REPLAN_REQUEST],
}


# ── Message Model ──────────────────────────────────────────────────────────────

class AgentMessage(BaseModel):
    """Structured message passed between agents via the MessageBus."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    sender: str                  # agent_name of the sender
    receiver: str                # agent_name of the intended recipient (or "all")
    message_type: str            # one of MessageType values
    content: str                 # human-readable summary of the message
    metadata: Dict = Field(default_factory=dict)  # structured data payload
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_ws_event(self) -> Dict:
        """Serialize to the WebSocket event format for frontend consumption."""
        return {
            "event_type": "agent:message",
            "incident_id": self.incident_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    def to_audit_event(self) -> Dict:
        """Serialize to the audit trail event format."""
        return {
            "event_type": "agent_message",
            "actor_type": "agent",
            "actor_id": self.sender,
            "event_data": {
                "receiver": self.receiver,
                "message_type": self.message_type,
                "content": self.content,
                "metadata": self.metadata,
                "message_id": self.id,
            },
        }


# ── Message Bus ────────────────────────────────────────────────────────────────

class MessageBus:
    """
    In-memory pub/sub message bus for inter-agent communication.

    Agents send typed messages to named receivers. The Commander reads
    all messages for an incident to understand cross-agent context.
    No external dependencies — pure Python dict.
    """

    def __init__(self):
        # incident_id → ordered list of AgentMessages
        self._store: Dict[str, List[AgentMessage]] = {}

    # ── Write ──────────────────────────────────────────────────────────────────

    def send_message(self, message: AgentMessage) -> AgentMessage:
        """Publish a message from one agent to another."""
        if message.incident_id not in self._store:
            self._store[message.incident_id] = []
        self._store[message.incident_id].append(message)
        return message

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_messages(
        self,
        incident_id: str,
        *,
        receiver: Optional[str] = None,
        sender: Optional[str] = None,
        message_type: Optional[str] = None,
    ) -> List[AgentMessage]:
        """
        Retrieve messages for an incident, with optional filters.

        Parameters
        ----------
        incident_id  : Target incident.
        receiver     : Only return messages addressed to this agent.
        sender       : Only return messages from this agent.
        message_type : Only return messages of this type.
        """
        msgs = list(self._store.get(incident_id, []))
        if receiver:
            msgs = [m for m in msgs if m.receiver in (receiver, "all")]
        if sender:
            msgs = [m for m in msgs if m.sender == sender]
        if message_type:
            msgs = [m for m in msgs if m.message_type == message_type]
        return msgs

    def get_conversation(self, incident_id: str) -> List[AgentMessage]:
        """Return the full, ordered message log for an incident."""
        return list(self._store.get(incident_id, []))

    def get_conversation_dicts(self, incident_id: str) -> List[Dict]:
        """Return the full message log as serialized dicts (for API responses)."""
        return [m.model_dump() for m in self.get_conversation(incident_id)]

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def clear_incident_messages(self, incident_id: str) -> None:
        """Remove all messages for a completed or cancelled incident."""
        self._store.pop(incident_id, None)

    def message_count(self, incident_id: str) -> int:
        """Return total messages exchanged for an incident."""
        return len(self._store.get(incident_id, []))


# ── Singleton ──────────────────────────────────────────────────────────────────
message_bus = MessageBus()
