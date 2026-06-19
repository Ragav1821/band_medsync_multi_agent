#!/usr/bin/env python3
"""
Phase 20.5 — Demo Video Pre-Generation Script
Generates 3 demo executive briefing videos for use during judging/presentation.

Usage:
    python scripts/generate_demo_videos.py

Output:
    media/demo/mass-casualty-demo.mp4
    media/demo/icu-saturation-demo.mp4
    media/demo/pandemic-surge-demo.mp4

Run once before your demo. Videos load instantly during judging.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("demo-generator")

DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "media", "demo")

# ── Demo incident scenarios ────────────────────────────────────────────────────

DEMO_INCIDENTS = [
    {
        "id": "demo-mass-casualty",
        "output_name": "mass-casualty-demo.mp4",
        "label": "Mass Casualty Event",
        "incident": {
            "id": "demo-mass-casualty",
            "incident_type": "mass_casualty",
            "incoming_patients": 35,
            "icu_occupancy_pct": 92.0,
            "ed_occupancy_pct": 88.0,
            "available_nurses": 8,
            "available_ventilators": 4,
            "blood_bank_units": 120,
            "severity_level": 3,
            "created_at": "2026-01-15T08:30:00Z",
        },
        "action_plan": {
            "compliance_status": "VALIDATED",
            "priority_1_actions": [
                {"description": "Activate Mass Casualty Protocol — divert all non-critical ED patients", "timeframe": "Immediate"},
                {"description": "Emergency nurse call-in — activate 12 additional staff from on-call roster", "timeframe": "Immediate"},
            ],
            "priority_2_actions": [
                {"description": "Request mutual aid from Regional Medical Center", "timeframe": "15 minutes"},
            ],
        },
        "coordination_round": {
            "revision_count": 2,
            "replan_count": 1,
            "negotiation_log": [
                {"agent": "compliance", "event": "REVISION_REQUEST", "reason": "Nurse-to-patient ratio below JCAHO minimum"},
                {"agent": "commander", "event": "REPLAN_LAUNCHED"},
                {"agent": "compliance", "event": "VALIDATED", "result": "All regulatory requirements met"},
            ],
        },
    },
    {
        "id": "demo-icu-saturation",
        "output_name": "icu-saturation-demo.mp4",
        "label": "ICU Saturation",
        "incident": {
            "id": "demo-icu-saturation",
            "incident_type": "icu_overflow",
            "incoming_patients": 12,
            "icu_occupancy_pct": 98.0,
            "ed_occupancy_pct": 95.0,
            "available_nurses": 3,
            "available_ventilators": 1,
            "blood_bank_units": 60,
            "severity_level": 3,
            "created_at": "2026-01-15T14:15:00Z",
        },
        "action_plan": {
            "compliance_status": "VALIDATED",
            "priority_1_actions": [
                {"description": "Immediate transfer protocol: 3 stable ICU patients to step-down unit", "timeframe": "Immediate"},
                {"description": "Activate ventilator sharing protocol per FEMA guidance", "timeframe": "Immediate"},
            ],
            "priority_2_actions": [
                {"description": "Contact regional ventilator stockpile for emergency deployment", "timeframe": "15 minutes"},
            ],
        },
        "coordination_round": {
            "revision_count": 3,
            "replan_count": 2,
            "negotiation_log": [
                {"agent": "compliance", "event": "REVISION_REQUEST", "reason": "Ventilator sharing requires ethics board sign-off"},
                {"agent": "commander", "event": "REPLAN_LAUNCHED"},
                {"agent": "compliance", "event": "VALIDATED", "result": "Ethics exemption confirmed per emergency protocol"},
            ],
        },
    },
    {
        "id": "demo-pandemic-surge",
        "output_name": "pandemic-surge-demo.mp4",
        "label": "Pandemic Surge",
        "incident": {
            "id": "demo-pandemic-surge",
            "incident_type": "pandemic_surge",
            "incoming_patients": 60,
            "icu_occupancy_pct": 87.0,
            "ed_occupancy_pct": 91.0,
            "available_nurses": 15,
            "available_ventilators": 8,
            "blood_bank_units": 200,
            "severity_level": 3,
            "created_at": "2026-01-15T20:00:00Z",
        },
        "action_plan": {
            "compliance_status": "VALIDATED",
            "priority_1_actions": [
                {"description": "Activate pandemic surge overflow area — gymnasium converted to ward", "timeframe": "Immediate"},
                {"description": "Deploy rapid testing stations at all entry points", "timeframe": "Immediate"},
            ],
            "priority_2_actions": [
                {"description": "Coordinate with public health for community isolation centers", "timeframe": "1 hour"},
            ],
        },
        "coordination_round": {
            "revision_count": 1,
            "replan_count": 0,
            "negotiation_log": [
                {"agent": "compliance", "event": "VALIDATED", "result": "Pandemic protocol fully compliant"},
            ],
        },
    },
]


async def generate_demo(scenario: dict) -> None:
    """Generate one demo video for a given scenario."""
    from agents.video.storytelling_agent import StorytellingAgent
    from agents.video.script_agent import ScriptAgent
    from agents.video.storyboard_agent import StoryboardAgent
    from agents.video.voiceover_agent import VoiceoverAgent
    from agents.video.visual_agent import VisualAgent
    from agents.video.composition_agent import CompositionAgent

    label = scenario["label"]
    incident = scenario["incident"]
    action_plan = scenario["action_plan"]
    coordination_round = scenario["coordination_round"]
    output_name = scenario["output_name"]
    output_path = os.path.join(DEMO_DIR, output_name)

    # Skip if already exists
    if os.path.exists(output_path) and os.path.getsize(output_path) > 100_000:
        logger.info("[%s] Already exists (%s) — skipping", label, output_path)
        return

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("[%s] Starting generation...", label)

    # Stage 1: Story
    story = await StorytellingAgent().run(
        incident=incident,
        action_plan=action_plan,
        agent_outputs={},
        coordination_round=coordination_round,
        audit_events=[],
    )
    logger.info("[%s] Story: %s", label, story.get("title", "")[:50])

    # Stage 2: Script (90s target for demos)
    script = await ScriptAgent().run(story, target_duration_sec=90)
    logger.info("[%s] Script: %d sections, ~%ds", label, len(script.get("sections", [])), script.get("estimated_duration_sec", 0))

    # Stage 3: Storyboard
    storyboard = await StoryboardAgent().run(
        script, incident,
        action_plan=action_plan,
        coordination_round=coordination_round,
    )
    logger.info("[%s] Storyboard: %d scenes", label, storyboard.get("total_scenes"))

    # Stage 4: Voice-over
    audio_result = await VoiceoverAgent().run(script, incident["id"])
    audio_path = audio_result.get("audio_path", "")
    logger.info("[%s] Audio: %s (%d bytes)", label, audio_result.get("provider"), os.path.getsize(audio_path) if audio_path else 0)

    # Stage 5: Visuals
    visual_result = await VisualAgent().run(storyboard, incident, action_plan)
    frame_paths = visual_result.get("frame_paths", [])
    logger.info("[%s] Visuals: %d frames", label, len(frame_paths))

    # Stage 6: Composition — write to demo dir
    comp_agent = CompositionAgent()
    # Temporarily override output to demo dir
    import shutil
    temp_result = await comp_agent.run(
        frame_paths=frame_paths,
        audio_path=audio_path,
        storyboard=storyboard,
        incident_id=incident["id"],
    )
    # Copy to demo directory
    temp_path = temp_result.get("output_path", "")
    if temp_path and os.path.exists(temp_path):
        shutil.copy2(temp_path, output_path)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info("[%s] ✅ Demo video: %s (%.1f MB)", label, output_name, size_mb)
    else:
        logger.error("[%s] ❌ Composition failed: %s", label, temp_result.get("error", "unknown"))


async def main():
    os.makedirs(DEMO_DIR, exist_ok=True)
    logger.info("MedSync AI — Demo Video Pre-Generator")
    logger.info("Output directory: %s", DEMO_DIR)
    logger.info("Generating %d demo scenarios...\n", len(DEMO_INCIDENTS))

    results = []
    for scenario in DEMO_INCIDENTS:
        try:
            await generate_demo(scenario)
            results.append((scenario["label"], "✅ SUCCESS"))
        except Exception as exc:
            logger.error("[%s] Failed: %s", scenario["label"], exc)
            results.append((scenario["label"], f"❌ FAILED: {exc}"))

    logger.info("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("RESULTS:")
    for label, status in results:
        logger.info("  %-30s %s", label, status)
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("Demo videos ready in: %s", DEMO_DIR)


if __name__ == "__main__":
    asyncio.run(main())
