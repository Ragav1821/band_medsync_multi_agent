# -*- coding: utf-8 -*-
"""
Comprehensive serialization tests for the video job status endpoint.

Tests that all job states (pending, processing, completed, failed) serialize
cleanly through _sanitize_job() with no numpy types surviving into the result.

Run:  python -X utf8 test_numpy_serialization.py
  or: python test_numpy_serialization.py  (Windows — ASCII output)
"""
import io
import os
import sys
import json

# Force UTF-8 stdout on Windows so tick/cross symbols render correctly
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from shared.utils import sanitize_for_json
from routers.video_router import _sanitize_job
from shared.schemas import VideoJobStatus


def _assert_no_numpy(obj, path: str = "root") -> None:
    """Recursively assert that no numpy types exist in obj."""
    type_name = type(obj).__name__
    module = type(obj).__module__ or ""
    assert not module.startswith("numpy"), (
        f"numpy type found at path '{path}': {type_name} = {repr(obj)}"
    )
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_numpy(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_no_numpy(v, f"{path}[{i}]")


def _assert_json_serializable(obj, label: str) -> None:
    """Assert that obj can be serialized to JSON without errors."""
    try:
        json.dumps(obj)
    except (TypeError, ValueError) as e:
        raise AssertionError(f"JSON serialization failed for '{label}': {e}")


def run_tests():
    print("=" * 60)
    print("MedSync AI — numpy serialization tests")
    print("=" * 60)
    
    failures = []

    # ── Scenario 1: PENDING job ───────────────────────────────────────────────
    job_pending = {
        "id": "job_pending_001",
        "incident_id": "inc_001",
        "status": VideoJobStatus.PENDING,
        "progress_pct": np.int64(0),
        "voice_provider": "edge_tts",
        "created_at": "2026-06-19T04:00:00",
        "completed_at": None,
        "duration_sec": None,
        "error_message": None,
        "output_path": None,
    }

    # ── Scenario 2: PROCESSING job with storyboard numpy values ──────────────
    job_processing = {
        "id": "job_proc_002",
        "incident_id": "inc_002",
        "status": VideoJobStatus.STORYBOARD,
        "progress_pct": np.int64(40),
        "voice_provider": "edge_tts",
        "created_at": "2026-06-19T04:00:01",
        "completed_at": None,
        "duration_sec": None,
        "error_message": None,
        "output_path": None,
        "story_json": {
            "title": "Test Story",
            "hook": "A crisis unfolded.",
            "sections": [{"section_id": "problem", "title": "The Crisis", "narrative": "..."}],
            "business_impact": {"agents_deployed": np.int64(5), "audit_ready": True},
        },
        "script_json": {
            "total_words": np.int64(250),
            "estimated_duration_sec": np.int64(116),
            "sections": [
                {
                    "section_id": "problem",
                    "duration_sec": np.int64(18),
                    "script_text": "Test narration.",
                }
            ],
        },
        "storyboard_json": {
            "total_scenes": np.int64(9),
            "total_duration_sec": np.float64(138.0),
            "scenes": [
                {
                    "scene_num": np.int64(1),
                    "duration_sec": np.int64(10),
                    "section_id": "intro",
                    "title": "MedSync AI",
                }
            ],
            "trust_indicators": {"human_review_required": True, "ai_generated": True},
        },
    }

    # ── Scenario 3: COMPLETED job — moviepy returns numpy.float64 for duration ─
    job_completed = {
        "id": "job_comp_003",
        "incident_id": "inc_003",
        "status": VideoJobStatus.COMPLETED,
        "progress_pct": np.int64(100),
        "voice_provider": "edge_tts",
        "created_at": "2026-06-19T04:00:02",
        "completed_at": "2026-06-19T04:02:10",
        # This is the EXACT type that MoviePy 2.x returns for video.duration
        "duration_sec": np.float64(138.4),
        "error_message": None,
        "output_path": "/fake/path/incident-briefing-inc_003.mp4",
        "script_json": {
            "total_words": np.int64(310),
            "estimated_duration_sec": np.float64(143.0),
            "sections": [
                {"section_id": "intro",  "duration_sec": np.int64(12), "script_text": "..."},
                {"section_id": "problem", "duration_sec": np.int64(18), "script_text": "..."},
            ],
        },
        "storyboard_json": {
            "total_scenes": np.int64(9),
            "total_duration_sec": np.float64(138.0),
            "scenes": [
                {"scene_num": np.int64(1), "duration_sec": np.int64(10), "section_id": "intro"},
                {"scene_num": np.int64(2), "duration_sec": np.int64(18), "section_id": "problem"},
            ],
            "trust_indicators": {},
        },
    }

    # ── Scenario 4: FAILED job ────────────────────────────────────────────────
    job_failed = {
        "id": "job_fail_004",
        "incident_id": "inc_004",
        "status": VideoJobStatus.FAILED,
        "progress_pct": np.int64(75),
        "voice_provider": "edge_tts",
        "created_at": "2026-06-19T04:00:03",
        "completed_at": "2026-06-19T04:01:00",
        "duration_sec": None,
        "error_message": "Video composition failed: FFmpeg not found",
        "output_path": None,
    }

    scenarios = [
        (1, "PENDING",    job_pending),
        (2, "PROCESSING", job_processing),
        (3, "COMPLETED",  job_completed),
        (4, "FAILED",     job_failed),
    ]

    for num, label, job in scenarios:
        print(f"\n--- Scenario {num}: {label} ---")
        try:
            sanitized = _sanitize_job(job)

            # 1. Verify no numpy types in the entire result
            _assert_no_numpy(sanitized, label)
            print(f"  ✓ No numpy types in result")

            # 2. Verify JSON serializable
            _assert_json_serializable(sanitized, label)
            print(f"  ✓ JSON serializable")

            # 3. Spot-check key field types
            progress = sanitized.get("progress_pct")
            if progress is not None:
                assert type(progress) is int, f"progress_pct must be int, got {type(progress)}"
                print(f"  ✓ progress_pct={progress} is int")

            duration = sanitized.get("duration_sec")
            if duration is not None:
                assert isinstance(duration, (int, float)) and type(duration).__module__ == "builtins", \
                    f"duration_sec must be Python float, got {type(duration)}"
                print(f"  ✓ duration_sec={duration} is Python float")

            # 4. Check nested storyboard scenes
            storyboard = sanitized.get("storyboard")
            if storyboard:
                scenes = storyboard.get("scenes", [])
                for i, scene in enumerate(scenes):
                    d = scene.get("duration_sec")
                    if d is not None:
                        assert type(d).__module__ == "builtins", \
                            f"storyboard.scenes[{i}].duration_sec is numpy: {type(d)}"
                print(f"  ✓ storyboard.scenes[*].duration_sec all Python types")

            print(f"  ✓ PASS")

        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failures.append(f"Scenario {num} ({label}): {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failures.append(f"Scenario {num} ({label}): {e}")

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {len(failures)} test(s) failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print(f"ALL PASSED: {len(scenarios)} scenarios serialized successfully")
        print("=" * 60)


if __name__ == "__main__":
    run_tests()
