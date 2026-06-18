"""
Band of Agents — Real Integration Service
==========================================

Replaces the previous stub with live calls to https://app.band.ai/api/v1

Architecture:
- Each MedSync agent maps to a registered Band Remote Agent with its own API key.
- On incident creation the Commander creates a Band Chat Room.
- Each agent posts a structured message to that room at its lifecycle point.
- Messages are routed via @mention to the next agent in the chain.
- Human approval fires a final Band escalation post.

API reference: https://docs.band.ai/api/agent-api
Auth header:   X-API-Key: <per-agent-api-key>
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent registry — maps internal agent names to Band credentials
# ---------------------------------------------------------------------------

AGENT_REGISTRY: dict[str, dict] = {
    "incident_commander": {
        "api_key":  settings.band_commander_api_key,
        "agent_id": settings.band_commander_agent_id,
        "handle":   settings.band_commander_handle,
        "name":     "Incident Commander",
        "emoji":    "🎯",
    },
    "capacity_agent": {
        "api_key":  settings.band_capacity_api_key,
        "agent_id": settings.band_capacity_agent_id,
        "handle":   settings.band_capacity_handle,
        "name":     "Capacity Agent",
        "emoji":    "🏥",
    },
    "staffing_agent": {
        "api_key":  settings.band_staffing_api_key,
        "agent_id": settings.band_staffing_agent_id,
        "handle":   settings.band_staffing_handle,
        "name":     "Staffing Agent",
        "emoji":    "👩‍⚕️",
    },
    "resource_agent": {
        "api_key":  settings.band_resource_api_key,
        "agent_id": settings.band_resource_agent_id,
        "handle":   settings.band_resource_handle,
        "name":     "Resource Agent",
        "emoji":    "📦",
    },
    "compliance_agent": {
        "api_key":  settings.band_compliance_api_key,
        "agent_id": settings.band_compliance_agent_id,
        "handle":   settings.band_compliance_handle,
        "name":     "Compliance Agent",
        "emoji":    "⚖️",
    },
}

# ---------------------------------------------------------------------------
# Room registry — incident_id → band_chat_id (in-memory for MVP)
# ---------------------------------------------------------------------------
_room_registry: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Public API — Room lifecycle
# ---------------------------------------------------------------------------

async def create_band_room(incident_id: str, title: str) -> Optional[str]:
    """
    Create a Band Chat Room for an incident and invite all specialist agents.
    Called by the Commander when a new incident is created.

    Returns the Band chat_id (UUID) or None if the call fails.
    """
    api_key = AGENT_REGISTRY["incident_commander"]["api_key"]
    url = f"{settings.band_api_base}/agent/chats"

    payload = {
        "chat": {
            "title": f"MedSync | {title} | {incident_id[:8].upper()}",
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            chat_id = data["data"]["id"]
            _room_registry[incident_id] = chat_id
            logger.info(
                "[BandService] Room created: incident=%s band_chat_id=%s",
                incident_id, chat_id,
            )

            # Invite all specialist agents in parallel
            await _invite_all_agents(chat_id, api_key, client)

            return chat_id

    except Exception as exc:
        logger.warning(
            "[BandService] create_band_room failed (non-fatal): %s", exc
        )
        return None


async def _invite_all_agents(chat_id: str, commander_api_key: str, client: httpx.AsyncClient) -> None:
    """
    Add all 4 specialist agents as participants in the Band room.
    Must be called with the Commander's API key (room creator = owner).
    Uses participant_id field as documented in Band API v1.
    """
    url = f"{settings.band_api_base}/agent/chats/{chat_id}/participants"
    specialists = ["capacity_agent", "staffing_agent", "resource_agent", "compliance_agent"]

    async def add_one(agent_key: str) -> None:
        pid = AGENT_REGISTRY[agent_key]["agent_id"]
        try:
            resp = await client.post(
                url,
                headers={"X-API-Key": commander_api_key, "Content-Type": "application/json"},
                json={"participant": {"participant_id": pid}},
            )
            if resp.status_code == 201:
                logger.info("[BandService] Added %s to room %s", agent_key, chat_id[:8])
            else:
                logger.warning(
                    "[BandService] Failed to add %s: HTTP %s %s",
                    agent_key, resp.status_code, resp.text[:100],
                )
        except Exception as exc:
            logger.warning("[BandService] Error adding %s: %s", agent_key, exc)

    await asyncio.gather(*[add_one(k) for k in specialists])


def get_band_room(incident_id: str) -> Optional[str]:
    """Return the Band chat_id for an incident, or None if not created."""
    return _room_registry.get(incident_id)


# ---------------------------------------------------------------------------
# Public API — Agent messaging
# ---------------------------------------------------------------------------

async def post_agent_message(
    incident_id: str,
    sender_agent: str,
    message_type: str,
    content: str,
    mention_agent: str = "incident_commander",
) -> dict:
    """
    Post a structured coordination message to the incident's Band room.

    Parameters
    ----------
    incident_id   : str  — the incident this message relates to
    sender_agent  : str  — key from AGENT_REGISTRY (e.g. "capacity_agent")
    message_type  : str  — DISPATCH | REPORT | COMPLIANCE | PLAN_READY | APPROVED | ESCALATION
    content       : str  — the human-readable message body
    mention_agent : str  — which agent to @mention (routes delivery)

    Returns
    -------
    dict with status, message_id, etc.
    """
    chat_id = get_band_room(incident_id)
    if not chat_id:
        logger.debug(
            "[BandService] No Band room for incident %s — skipping message", incident_id
        )
        return {"status": "skipped", "reason": "no_band_room"}

    sender = AGENT_REGISTRY.get(sender_agent)
    recipient = AGENT_REGISTRY.get(mention_agent)

    if not sender or not recipient:
        logger.warning("[BandService] Unknown agent key: sender=%s mention=%s", sender_agent, mention_agent)
        return {"status": "error", "reason": "unknown_agent"}

    # Band requires at least one @mention and the sender cannot mention itself
    if sender_agent == mention_agent:
        # Fall back to mentioning commander if agent would mention itself
        mention_agent = "incident_commander"
        recipient = AGENT_REGISTRY["incident_commander"]
        # If sender IS commander, mention capacity instead
        if sender_agent == "incident_commander":
            mention_agent = "capacity_agent"
            recipient = AGENT_REGISTRY["capacity_agent"]

    recipient_handle = recipient["handle"]  # e.g. "1821ragav/capacity-agent"
    recipient_id     = recipient["agent_id"]

    formatted_content = (
        f"[{message_type}] {sender['emoji']} {sender['name'].upper()}\n"
        f"Incident: #{incident_id[:8].upper()}\n"
        f"{content}\n"
        f"@{recipient_handle.split('/')[-1]}"
    )

    url = f"{settings.band_api_base}/agent/chats/{chat_id}/messages"
    payload = {
        "message": {
            "content": formatted_content,
            "mentions": [
                {
                    "id":     recipient_id,
                    "handle": recipient_handle,
                    "name":   recipient["name"],
                    "kind":   "mention",
                }
            ],
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                headers={
                    "X-API-Key": sender["api_key"],
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            message_id = data.get("data", {}).get("id", "unknown")
            logger.info(
                "[BandService] Message sent: %s → %s [%s] message_id=%s",
                sender_agent, mention_agent, message_type, message_id,
            )
            return {
                "status": "sent",
                "message_id": message_id,
                "sender": sender_agent,
                "recipient": mention_agent,
                "message_type": message_type,
                "chat_id": chat_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

    except httpx.HTTPStatusError as exc:
        logger.error(
            "[BandService] HTTP %s posting message (%s→%s): %s",
            exc.response.status_code, sender_agent, mention_agent, exc.response.text[:200],
        )
        return {
            "status": "error",
            "http_status": exc.response.status_code,
            "error": exc.response.text[:200],
        }
    except Exception as exc:
        logger.error("[BandService] Unexpected error posting message: %s", exc)
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Public API — Legacy escalation (kept for backward compatibility)
# ---------------------------------------------------------------------------

async def send_escalation_to_band(
    incident_id: str,
    plan_id: str,
    message: str,
    approved_by: str = "system",
) -> dict:
    """
    Send a post-approval escalation to the Band room.
    This is the main human-approval notification.

    Falls back gracefully if Band room does not exist.
    """
    import uuid
    notification_id = f"band-{incident_id[:8]}-{str(uuid.uuid4())[:8]}"

    escalation_content = (
        f"✅ PLAN APPROVED by {approved_by}\n"
        f"Plan ID: {plan_id[:8]}\n"
        f"Action: {message}\n"
        f"Status: EXECUTING"
    )

    result = await post_agent_message(
        incident_id=incident_id,
        sender_agent="incident_commander",
        message_type="APPROVED",
        content=escalation_content,
        mention_agent="compliance_agent",
    )

    _log_audit(incident_id, notification_id, message, approved_by,
               status=result.get("status", "error"))

    return {
        "status":          result.get("status", "error"),
        "channel":         "band",
        "message":         message,
        "notification_id": notification_id,
        "band_message_id": result.get("message_id"),
        "timestamp":       datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log_audit(
    incident_id: str,
    notification_id: str,
    message: str,
    approved_by: str,
    status: str,
) -> None:
    """Write Band notification event to the in-memory audit trail."""
    try:
        from services.data_store import store
        store._log_audit(
            incident_id=incident_id,
            event_type="band_notification_sent",
            actor_type="system",
            actor_id="band_service",
            data={
                "notification_id": notification_id,
                "message_preview": message[:100],
                "approved_by": approved_by,
                "status": status,
            },
        )
    except Exception as exc:
        logger.warning("[BandService] Audit log failed (non-fatal): %s", exc)
