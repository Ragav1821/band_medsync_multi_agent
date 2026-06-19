"""
Phase 20 — Video Composition Agent
Combines scene images + voice-over audio into the final incident-briefing.mp4 using MoviePy.
Falls back to a slide-show style video if advanced features unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_VIDEOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "videos"
)


class CompositionAgent:
    """
    Input : frame_paths (list of PNG paths), audio_path (MP3), storyboard (for timings)
    Output: path to incident-briefing-{incident_id}.mp4
    """

    def __init__(self):
        os.makedirs(_VIDEOS_DIR, exist_ok=True)
        self._moviepy_available = False
        try:
            # MoviePy 2.x removed `moviepy.editor` — import directly from `moviepy`
            from moviepy import ImageClip  # noqa: F401
            self._moviepy_available = True
        except ImportError:
            logger.warning("[CompositionAgent] MoviePy not installed — will use FFmpeg fallback")


    async def run(
        self,
        frame_paths: List[str],
        audio_path: str,
        storyboard: Dict,
        incident_id: str,
    ) -> Dict:
        logger.info("[CompositionAgent] Composing video for incident %s with %d frames", incident_id, len(frame_paths))

        output_path = os.path.join(_VIDEOS_DIR, f"incident-briefing-{incident_id}.mp4")
        scenes = storyboard.get("scenes", [])

        try:
            if self._moviepy_available:
                result = await self._compose_moviepy(frame_paths, audio_path, scenes, output_path)
            else:
                result = await self._compose_ffmpeg(frame_paths, audio_path, scenes, output_path)

            logger.info("[CompositionAgent] Video written: %s (%s bytes)", output_path, os.path.getsize(output_path) if os.path.exists(output_path) else "?")
            return result

        except Exception as exc:
            logger.error("[CompositionAgent] Composition failed: %s", exc)
            # Final fallback: create a bare video from images
            try:
                result = await self._compose_ffmpeg(frame_paths, audio_path, scenes, output_path)
                return result
            except Exception as exc2:
                logger.error("[CompositionAgent] FFmpeg fallback also failed: %s", exc2)
                return {
                    "output_path": output_path,
                    "duration_sec": storyboard.get("total_duration_sec", 120),
                    "resolution": "1280x720",
                    "format": "mp4",
                    "error": str(exc2),
                    "status": "failed",
                }

    async def _compose_moviepy(
        self,
        frame_paths: List[str],
        audio_path: str,
        scenes: List[Dict],
        output_path: str,
    ) -> Dict:
        """Compose video using MoviePy with crossfade transitions and audio."""
        import asyncio

        def _sync_compose():
            from moviepy import (
                ImageClip,
                AudioFileClip,
                concatenate_videoclips,
                CompositeVideoClip,
            )

            clips = []
            for i, (frame_path, scene) in enumerate(zip(frame_paths, scenes)):
                duration = scene.get("duration_sec", 15)
                if not os.path.exists(frame_path):
                    continue
                clip = ImageClip(frame_path, duration=duration)

                # ── Task 7: Ken Burns subtle zoom (1.0 → 1.04 over scene duration) ──
                try:
                    from moviepy import vfx
                    # Gentle zoom-in: scale starts at 1.0, ends at 1.04 (4% zoom)
                    zoom_factor = 1.04
                    clip = clip.with_effects([
                        vfx.Resize(lambda t: 1 + (zoom_factor - 1) * (t / max(duration, 1)))
                    ])
                except Exception:
                    pass  # Ken Burns optional — skip silently if unavailable

                clips.append(clip)

            if not clips:
                raise ValueError("No valid frame clips to compose")

            # Concatenate clips
            video = concatenate_videoclips(clips)

            # Add audio (MoviePy 2.x compatible)
            if audio_path and os.path.exists(audio_path):
                try:
                    audio = AudioFileClip(audio_path)
                    if audio.duration > video.duration:
                        audio = audio.with_end(video.duration)
                    video = video.with_audio(audio)
                except Exception as ae:
                    logger.warning("[CompositionAgent] Audio attach failed: %s", ae)

            video.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                logger=None,
                threads=2,
            )
            # Cast explicitly: MoviePy 2.x returns numpy.float64 for .duration,
            # which crashes Pydantic's TypeAdapter.dump_json() serializer.
            return float(video.duration)



        loop = asyncio.get_event_loop()
        duration = await loop.run_in_executor(None, _sync_compose)

        return {
            "output_path": output_path,
            "duration_sec": duration,
            "resolution": "1280x720",
            "format": "mp4",
            "status": "completed",
            "method": "moviepy",
        }

    async def _compose_ffmpeg(
        self,
        frame_paths: List[str],
        audio_path: str,
        scenes: List[Dict],
        output_path: str,
    ) -> Dict:
        """Compose video using FFmpeg directly via subprocess."""
        import asyncio
        import subprocess
        import tempfile

        # Write concat list file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            concat_file = f.name
            for frame_path, scene in zip(frame_paths, scenes):
                if os.path.exists(frame_path):
                    duration = scene.get("duration_sec", 15)
                    f.write(f"file '{frame_path.replace(os.sep, '/')}'\n")
                    f.write(f"duration {duration}\n")
            # Repeat last frame to avoid stuttering at end
            if frame_paths and os.path.exists(frame_paths[-1]):
                f.write(f"file '{frame_paths[-1].replace(os.sep, '/')}'\n")

        total_duration = sum(s.get("duration_sec", 15) for s in scenes)

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
        ]

        # Add audio if available
        has_audio = audio_path and os.path.exists(audio_path)
        if has_audio:
            cmd += ["-i", audio_path]

        cmd += [
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-r", "24",
        ]

        if has_audio:
            cmd += ["-c:a", "aac", "-shortest"]

        cmd += [output_path]

        def _run_ffmpeg():
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
            return result

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _run_ffmpeg)
        finally:
            try:
                os.unlink(concat_file)
            except Exception:
                pass

        actual_duration = total_duration
        if os.path.exists(output_path):
            try:
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                logger.info("[CompositionAgent] FFmpeg output: %.1f MB", size_mb)
            except Exception:
                pass

        return {
            "output_path": output_path,
            "duration_sec": actual_duration,
            "resolution": "1280x720",
            "format": "mp4",
            "status": "completed",
            "method": "ffmpeg",
        }
