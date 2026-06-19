"""
Phase 20 — Video Router
REST API endpoints for video generation jobs.
"""
from __future__ import annotations

import os
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from typing import List

import logging

from agents.video.video_pipeline import VideoPipeline, create_video_job
from services.data_store import store
from shared.schemas import VideoGenerateRequest, VideoJobStatus
from shared.utils import sanitize_for_json

logger = logging.getLogger(__name__)

video_router = APIRouter(tags=["Video Generator"])


# ── Generate Video ──────────────────────────────────────────────────────────

@video_router.post("/incidents/{incident_id}/generate-video", response_model=dict, status_code=201)
async def generate_video(
    incident_id: str,
    background_tasks: BackgroundTasks,
    body: VideoGenerateRequest | None = None,
):
    """
    Kick off the AI video generation pipeline for a completed incident.
    Returns immediately with a job_id. Poll GET /video-jobs/{job_id} for progress.
    """
    incident = store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    voice_provider = "edge_tts"
    target_duration_sec = 120
    if body:
        voice_provider = body.voice_provider or "edge_tts"
        target_duration_sec = body.target_duration_sec or 120

    # Create job record
    job = create_video_job(
        incident_id=incident_id,
        voice_provider=voice_provider,
        target_duration_sec=target_duration_sec,
    )

    # Run pipeline in background
    background_tasks.add_task(
        _run_pipeline,
        job_id=job["id"],
        incident_id=incident_id,
        voice_provider=voice_provider,
        target_duration_sec=target_duration_sec,
    )

    return {
        "job_id": job["id"],
        "incident_id": incident_id,
        "status": VideoJobStatus.PENDING,
        "message": "Video generation pipeline started. Poll /video-jobs/{job_id} for progress.",
        "poll_url": f"/api/v1/video-jobs/{job['id']}",
        "download_url": f"/api/v1/video-jobs/{job['id']}/download",
        "websocket_hint": f"/ws/incidents/{incident_id}",
    }


# ── Get Job Status ──────────────────────────────────────────────────────────

@video_router.get("/video-jobs/{job_id}", response_model=dict)
async def get_video_job(job_id: str):
    """Get the current status and partial results of a video generation job."""
    job = store.get_video_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return _sanitize_job(job)


# ── List Jobs for Incident ──────────────────────────────────────────────────

@video_router.get("/incidents/{incident_id}/video-jobs", response_model=List[dict])
async def list_video_jobs(incident_id: str):
    """List all video generation jobs for an incident, newest first."""
    jobs = store.list_video_jobs_for_incident(incident_id)
    return [_sanitize_job(j) for j in jobs]


# ── Download Video ──────────────────────────────────────────────────────────

@video_router.get("/video-jobs/{job_id}/download")
async def download_video(job_id: str):
    """Stream the generated MP4 video file as a download."""
    job = store.get_video_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    if job.get("status") != VideoJobStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Video not yet ready. Current status: {job.get('status')}",
        )

    output_path = job.get("output_path", "")
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Video file not found on server")

    incident_id = job.get("incident_id", "incident")[:8]
    filename = f"medsync-briefing-{incident_id}.mp4"

    return FileResponse(
        path=output_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Delete Job ──────────────────────────────────────────────────────────────

@video_router.delete("/video-jobs/{job_id}", response_model=dict)
async def delete_video_job(job_id: str):
    """Clean up a video job and its generated files."""
    job = store.get_video_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    # Remove video file
    output_path = job.get("output_path", "")
    if output_path and os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass

    # Remove audio file
    audio_path = job.get("audio_path", "")
    if audio_path and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except Exception:
            pass

    # Mark as deleted in store (soft delete)
    store.update_video_job_status(job_id, "deleted", {})
    return {"job_id": job_id, "message": "Video job and files deleted"}


# ── Internal helpers ────────────────────────────────────────────────────────

async def _run_pipeline(job_id: str, incident_id: str, voice_provider: str, target_duration_sec: int) -> None:
    """Background task: run the full video pipeline."""
    pipeline = VideoPipeline()
    await pipeline.run(
        job_id=job_id,
        incident_id=incident_id,
        voice_provider=voice_provider,
        target_duration_sec=target_duration_sec,
    )


def _sanitize_job(job: dict) -> dict:
    """Return a clean job dict suitable for the API response (omit huge JSON blobs unless complete)."""
    status = job.get("status")
    result = {
        "id": job.get("id"),
        "incident_id": job.get("incident_id"),
        "status": status,
        "progress_pct": job.get("progress_pct", 0),
        "voice_provider": job.get("voice_provider", "gtts"),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
        "duration_sec": job.get("duration_sec"),
        "error_message": job.get("error_message"),
        "has_video": bool(job.get("output_path") and os.path.exists(job.get("output_path", ""))),
    }

    # Include rich story/script/storyboard data once generated.
    # Each sub-dict is sanitized individually BEFORE assignment so nested
    # numpy values (e.g. scene duration_sec from MoviePy) cannot escape.
    if job.get("story_json"):
        story_raw = job["story_json"]
        result["story"] = sanitize_for_json({
            "title":          story_raw.get("title"),
            "hook":           story_raw.get("hook"),
            "section_count":  len(story_raw.get("sections", [])),
            "business_impact": story_raw.get("business_impact"),
        })
    if job.get("script_json"):
        script_raw = job["script_json"]
        result["script"] = sanitize_for_json({
            "total_words":           script_raw.get("total_words"),
            "estimated_duration_sec": script_raw.get("estimated_duration_sec"),
            "sections":              script_raw.get("sections", []),
        })
    if job.get("storyboard_json"):
        sb_raw = job["storyboard_json"]
        result["storyboard"] = sanitize_for_json({
            "total_scenes":      sb_raw.get("total_scenes"),
            "total_duration_sec": sb_raw.get("total_duration_sec"),
            "scenes":            sb_raw.get("scenes", []),
            "trust_indicators":  sb_raw.get("trust_indicators", {}),
        })

    # Final pass over the outer dict (catches any top-level numpy values)
    sanitized_result = sanitize_for_json(result)
    return sanitized_result

