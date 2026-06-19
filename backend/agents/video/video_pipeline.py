"""
Phase 20 — Video Pipeline Orchestrator
Chains all 6 video agents and persists progress as a VideoJob.
Broadcasts WebSocket events at each stage.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Dict, Optional

from agents.video.storytelling_agent import StorytellingAgent
from agents.video.script_agent import ScriptAgent
from agents.video.storyboard_agent import StoryboardAgent
from agents.video.voiceover_agent import VoiceoverAgent
from agents.video.visual_agent import VisualAgent
from agents.video.composition_agent import CompositionAgent
from services.data_store import store
from shared.schemas import VideoJobStatus

logger = logging.getLogger(__name__)


class VideoPipeline:
    """
    Orchestrates the 6-stage AI video generation pipeline.

    Job lifecycle:
        PENDING → STORY → SCRIPT → STORYBOARD → AUDIO → VISUALS → COMPOSING → COMPLETED
        (any stage can transition to FAILED on error)
    """

    _STAGE_PROGRESS = {
        VideoJobStatus.STORY:      10,
        VideoJobStatus.SCRIPT:     25,
        VideoJobStatus.STORYBOARD: 40,
        VideoJobStatus.AUDIO:      55,
        VideoJobStatus.VISUALS:    75,
        VideoJobStatus.COMPOSING:  90,
        VideoJobStatus.COMPLETED: 100,
    }

    def __init__(self):
        self.storytelling = StorytellingAgent()
        self.script       = ScriptAgent()
        self.storyboard   = StoryboardAgent()
        self.composition  = CompositionAgent()

    async def run(
        self,
        job_id: str,
        incident_id: str,
        voice_provider: str = "gtts",
        target_duration_sec: int = 120,
    ) -> None:
        """Full pipeline run. Updates job status after each agent completes."""
        logger.info("[VideoPipeline] Starting job %s for incident %s", job_id, incident_id)

        # ── Gather source data ──────────────────────────────────────────────
        incident = store.get_incident(incident_id)
        if not incident:
            await self._fail(job_id, incident_id, f"Incident {incident_id} not found")
            return

        action_plan = store.get_action_plan(incident_id) or {}
        agent_outputs = action_plan.get("agent_outputs", {})
        coordination_round = store.get_coordination_round(incident_id) or {}
        audit_events = store.get_audit_events(incident_id) or []

        # ── Stage 1: Storytelling ────────────────────────────────────────────
        await self._update(job_id, VideoJobStatus.STORY)
        try:
            story = await self.storytelling.run(
                incident=incident,
                action_plan=action_plan,
                agent_outputs=agent_outputs,
                coordination_round=coordination_round,
                audit_events=audit_events,
            )
        except Exception as exc:
            await self._fail(job_id, incident_id, f"Storytelling failed: {exc}")
            return

        # ── Stage 2: Script ──────────────────────────────────────────────────
        await self._update(job_id, VideoJobStatus.SCRIPT, {"story_json": story})
        try:
            script = await self.script.run(story, target_duration_sec=target_duration_sec)
        except Exception as exc:
            await self._fail(job_id, incident_id, f"Script generation failed: {exc}")
            return

        # ── Stage 3: Storyboard ──────────────────────────────────────────────
        await self._update(job_id, VideoJobStatus.STORYBOARD, {"script_json": script})
        try:
            storyboard = await self.storyboard.run(
                script, incident,
                action_plan=action_plan,
                coordination_round=coordination_round,
            )
        except Exception as exc:
            await self._fail(job_id, incident_id, f"Storyboard failed: {exc}")
            return

        # ── Stage 4: Voice-over ──────────────────────────────────────────────
        await self._update(job_id, VideoJobStatus.AUDIO, {"storyboard_json": storyboard})
        try:
            voiceover_agent = VoiceoverAgent(voice_provider=voice_provider)
            audio_result = await voiceover_agent.run(script, incident_id)
            audio_path = audio_result.get("audio_path", "")
        except Exception as exc:
            logger.warning("[VideoPipeline] Audio failed, continuing without audio: %s", exc)
            audio_path = ""

        # ── Stage 5: Visuals ─────────────────────────────────────────────────
        await self._update(job_id, VideoJobStatus.VISUALS, {"audio_path": audio_path})
        try:
            visual_agent = VisualAgent()
            visual_result = await visual_agent.run(storyboard, incident, action_plan)
            frame_paths = visual_result.get("frame_paths", [])
        except Exception as exc:
            await self._fail(job_id, incident_id, f"Visual generation failed: {exc}")
            return

        # ── Stage 6: Composition ─────────────────────────────────────────────
        await self._update(job_id, VideoJobStatus.COMPOSING)
        try:
            comp_result = await self.composition.run(
                frame_paths=frame_paths,
                audio_path=audio_path,
                storyboard=storyboard,
                incident_id=incident_id,
            )
        except Exception as exc:
            await self._fail(job_id, incident_id, f"Video composition failed: {exc}")
            return

        # ── Complete ─────────────────────────────────────────────────────────
        output_path = comp_result.get("output_path", "")
        duration_sec = comp_result.get("duration_sec", target_duration_sec)

        store.update_video_job_status(job_id, VideoJobStatus.COMPLETED, {
            "progress_pct": 100,
            "output_path": output_path,
            "audio_path": audio_path,
            "duration_sec": duration_sec,
            "completed_at": datetime.utcnow().isoformat(),
        })

        # Broadcast completion
        await self._broadcast(incident_id, {
            "event_type": "video:completed",
            "job_id": job_id,
            "incident_id": incident_id,
            "output_path": output_path,
            "duration_sec": duration_sec,
        })

        logger.info("[VideoPipeline] Job %s COMPLETED. Output: %s", job_id, output_path)

    async def _update(self, job_id: str, status: VideoJobStatus, extra: Optional[Dict] = None) -> None:
        """Update job status + progress and broadcast WebSocket event."""
        progress = self._STAGE_PROGRESS.get(status, 0)
        update = {"progress_pct": progress}
        if extra:
            update.update(extra)
        job = store.update_video_job_status(job_id, status, update)
        if job:
            await self._broadcast(job.get("incident_id", ""), {
                "event_type": "video:progress",
                "job_id": job_id,
                "status": status,
                "progress_pct": progress,
            })
        logger.info("[VideoPipeline] Job %s → %s (%d%%)", job_id, status, progress)

    async def _fail(self, job_id: str, incident_id: str, error: str) -> None:
        store.update_video_job_status(job_id, VideoJobStatus.FAILED, {
            "error_message": error,
            "completed_at": datetime.utcnow().isoformat(),
        })
        await self._broadcast(incident_id, {
            "event_type": "video:failed",
            "job_id": job_id,
            "error": error,
        })
        logger.error("[VideoPipeline] Job %s FAILED: %s", job_id, error)

    async def _broadcast(self, incident_id: str, payload: Dict) -> None:
        try:
            from shared.event_bus import ws_manager
            await ws_manager.broadcast_to_incident(incident_id, payload)
        except Exception as exc:
            logger.debug("[VideoPipeline] WS broadcast skipped: %s", exc)


def create_video_job(incident_id: str, voice_provider: str = "gtts", target_duration_sec: int = 120) -> Dict:
    """Create and persist a new video job record. Returns the job dict."""
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "incident_id": incident_id,
        "status": VideoJobStatus.PENDING,
        "progress_pct": 0,
        "story_json": None,
        "script_json": None,
        "storyboard_json": None,
        "output_path": None,
        "audio_path": None,
        "duration_sec": None,
        "error_message": None,
        "voice_provider": voice_provider,
        "target_duration_sec": target_duration_sec,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    store.save_video_job(job)
    return job
