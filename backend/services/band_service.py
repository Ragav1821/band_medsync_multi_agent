"""
Band Notification Service — Stub implementation.

Sends escalation notifications to a Band group channel when an action plan is approved.

Current state: Demo stub — logs to audit trail and returns a queued status.
Production state: Replace _post_to_band() with the real Band REST API call using
                  BAND_ACCESS_TOKEN and BAND_KEY from .env.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def send_escalation_to_band(
    incident_id: str,
    plan_id: str,
    message: str,
    approved_by: str = "system",
) -> dict:
    """
    Queue an escalation notification for Band.

    Parameters
    ----------
    incident_id : str   — the incident this notification relates to.
    plan_id     : str   — the approved action plan ID.
    message     : str   — the escalation message text.
    approved_by : str   — the human who approved the action plan.

    Returns
    -------
    dict with keys:
      status       : "sent" | "queued" | "error"
      channel      : "band"
      message      : the message that was sent
      notification_id : str
      timestamp    : ISO timestamp
    """
    notification_id = _generate_notification_id(incident_id)
    payload = _build_payload(incident_id, plan_id, message, approved_by)

    try:
        result = await _post_to_band(payload)
        logger.info(
            "[BandService] Notification queued: id=%s incident=%s",
            notification_id, incident_id,
        )

        # Log to audit trail
        _log_audit(incident_id, notification_id, message, approved_by, status="queued")

        return {
            "status": result["status"],
            "channel": "band",
            "message": message,
            "notification_id": notification_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("[BandService] Failed to send notification: %s", exc)
        _log_audit(incident_id, notification_id, message, approved_by, status="error")
        return {
            "status": "error",
            "channel": "band",
            "message": message,
            "notification_id": notification_id,
            "error": str(exc),
            "timestamp": datetime.utcnow().isoformat(),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_payload(
    incident_id: str,
    plan_id: str,
    message: str,
    approved_by: str,
) -> dict:
    """Build the Band API payload."""
    return {
        "incident_id": incident_id,
        "plan_id": plan_id,
        "message": (
            f"🚨 MedSync AI Escalation\n"
            f"Incident: {incident_id}\n"
            f"Approved by: {approved_by}\n"
            f"Action required: {message}"
        ),
        "timestamp": datetime.utcnow().isoformat(),
    }


async def _post_to_band(payload: dict) -> dict:
    """
    Post a message to Band.

    STUB — returns immediately with queued status.
    Replace this with a real httpx call when Band credentials are available:

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://openapi.band.us/v2/post/create",
                headers={"Authorization": f"Bearer {settings.band_access_token}"},
                json={
                    "band_key": settings.band_key,
                    "content": payload["message"],
                },
                timeout=10,
            )
            resp.raise_for_status()
            return {"status": "sent", "band_post_key": resp.json()["result_data"]["post_key"]}
    """
    logger.info("[BandService][STUB] Would send to Band: %s", payload["message"][:80])
    return {"status": "queued"}


def _generate_notification_id(incident_id: str) -> str:
    import uuid
    return f"band-{incident_id[:8]}-{str(uuid.uuid4())[:8]}"


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
    except Exception as exc:  # noqa: BLE001
        logger.warning("[BandService] Audit log failed (non-fatal): %s", exc)
