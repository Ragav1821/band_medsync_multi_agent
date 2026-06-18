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
