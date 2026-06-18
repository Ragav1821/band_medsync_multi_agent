"""
WebSocket Event Bus — broadcasts real-time agent events to connected clients.
"""
import asyncio
import json
from typing import Dict, Set, List, Any
from datetime import datetime
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # incident_id → set of connected WebSocket clients
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, incident_id: str):
        await websocket.accept()
        if incident_id not in self.active_connections:
            self.active_connections[incident_id] = set()
        self.active_connections[incident_id].add(websocket)

    def disconnect(self, websocket: WebSocket, incident_id: str):
        if incident_id in self.active_connections:
            self.active_connections[incident_id].discard(websocket)

    async def broadcast_to_incident(self, incident_id: str, event: Dict):
        """Send an event to all clients watching a specific incident."""
        if incident_id not in self.active_connections:
            return
        message = json.dumps({**event, "timestamp": datetime.utcnow().isoformat()})
        dead_connections = set()
        for connection in self.active_connections[incident_id]:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.add(connection)
        # Cleanup dead connections
        for dead in dead_connections:
            self.active_connections[incident_id].discard(dead)

    async def broadcast_to_all(self, event: Dict):
        """Send an event to ALL connected clients (global alerts)."""
        message = json.dumps({**event, "timestamp": datetime.utcnow().isoformat()})
        all_connections = set()
        for connections in self.active_connections.values():
            all_connections.update(connections)
        dead_connections = set()
        for connection in all_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.add(connection)


# Singleton
ws_manager = ConnectionManager()


async def emit_agent_started(incident_id: str, agent_name: str):
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "agent:started",
        "incident_id": incident_id,
        "agent_name": agent_name,
    })


async def emit_agent_thinking(incident_id: str, agent_name: str, step: str, content: str):
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "agent:thinking",
        "incident_id": incident_id,
        "agent_name": agent_name,
        "step": step,
        "content": content,
    })


async def emit_agent_completed(incident_id: str, agent_name: str, output: Dict, confidence: float):
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "agent:completed",
        "incident_id": incident_id,
        "agent_name": agent_name,
        "output_summary": output.get("summary", ""),
        "confidence": confidence,
        "flags": output.get("flags", []),
    })


async def emit_plan_ready(incident_id: str, action_plan_id: str, summary: str):
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "plan:ready",
        "incident_id": incident_id,
        "action_plan_id": action_plan_id,
        "summary": summary,
    })


async def emit_escalation(incident_id: str, level: str, message: str):
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "alert:escalation",
        "incident_id": incident_id,
        "level": level,
        "message": message,
        "requires_approval": True,
    })


async def emit_band_room_created(incident_id: str, band_chat_id: str):
    """Notify the frontend that a Band coordination room is live."""
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "band:room_created",
        "incident_id": incident_id,
        "band_chat_id": band_chat_id,
        "band_chat_url": f"https://app.band.ai/chats/{band_chat_id}",
    })


async def emit_agent_message(incident_id: str, sender: str, receiver: str,
                              message_type: str, content: str, metadata: Dict = None):
    """
    Phase 18: Broadcast a structured inter-agent message to all WebSocket clients.
    This is the core event that powers the Coordination Timeline UI.
    """
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "agent:message",
        "incident_id": incident_id,
        "sender": sender,
        "receiver": receiver,
        "message_type": message_type,
        "content": content,
        "metadata": metadata or {},
    })


# ── Phase 19A: Negotiation Loop Events ────────────────────────────────────────

async def emit_negotiation_revision_requested(
    incident_id: str, issues: List[str], round_num: int
):
    """Compliance issued a REVISION_REQUEST — plan needs revision."""
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "negotiation:revision_requested",
        "incident_id": incident_id,
        "issues": issues[:5],
        "round": round_num,
        "message": f"Compliance requested revision: {'; '.join(issues[:2])}",
    })


async def emit_negotiation_replanning_started(
    incident_id: str, replan_num: int, max_rounds: int = 3
):
    """Commander started a replan cycle — agents are revising."""
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "negotiation:replanning_started",
        "incident_id": incident_id,
        "replan_number": replan_num,
        "max_rounds": max_rounds,
        "message": f"Replan cycle {replan_num}/{max_rounds} initiated by Commander.",
    })


async def emit_negotiation_reapproved(
    incident_id: str, round_num: int, status: str = "approved"
):
    """Compliance re-evaluated and approved the revised plan."""
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "negotiation:reapproved",
        "incident_id": incident_id,
        "round": round_num,
        "status": status,
        "message": f"Compliance approved revised plan on round {round_num}.",
    })


async def emit_negotiation_completed(
    incident_id: str, final_status: str, rounds_used: int, replan_count: int
):
    """Negotiation loop finished — final verdict delivered."""
    await ws_manager.broadcast_to_incident(incident_id, {
        "event_type": "negotiation:completed",
        "incident_id": incident_id,
        "final_status": final_status,
        "rounds_used": rounds_used,
        "replan_count": replan_count,
        "message": f"Negotiation complete: {final_status.upper()} after {replan_count} replan cycle(s).",
    })

