"""
Phase 20 — Voice-over Agent
Converts the script text into an MP3 audio file.

Voice provider priority:
  1. edge_tts   — Microsoft neural voices (free, no API key, best quality)
  2. gtts       — Google TTS (free, robotic, fallback)
  3. elevenlabs — Premium (requires ELEVENLABS_API_KEY)
  4. silent     — Silent placeholder (last-resort fallback)

Edge TTS recommended voices:
  en-US-AriaNeural  — warm, professional female
  en-US-GuyNeural   — authoritative male
  en-US-JennyNeural — friendly female
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Media output directory (created if missing)
_AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "audio")

# Default Edge TTS voice — can be overridden via EDGE_TTS_VOICE env var
_DEFAULT_EDGE_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural")
_FALLBACK_EDGE_VOICES = ["en-US-GuyNeural", "en-US-JennyNeural", "en-GB-SoniaNeural"]


class VoiceoverAgent:
    """
    Input : ScriptSchema (sections with script_text), incident_id, voice_provider
    Output: path to generated voiceover.mp3, per-section timing list

    Supported voice_provider values:
        "edge_tts"   — Microsoft neural voice (recommended, free)
        "gtts"       — Google TTS (fallback)
        "elevenlabs" — ElevenLabs premium (requires API key)
    """

    def __init__(self, voice_provider: str = "edge_tts"):
        # Normalize legacy provider name
        if voice_provider == "gtts":
            # Try edge_tts first; fallback to gtts if edge_tts not installed
            self.voice_provider = "edge_tts"
            self._gtts_fallback = True
        else:
            self.voice_provider = voice_provider
            self._gtts_fallback = False
        os.makedirs(_AUDIO_DIR, exist_ok=True)

    async def run(self, script: Dict, incident_id: str) -> Dict:
        logger.info(
            "[VoiceoverAgent] Generating audio for incident %s via %s",
            incident_id, self.voice_provider,
        )

        # Build full script text from sections
        sections = script.get("sections", [])
        full_text = " ".join(s.get("script_text", "") for s in sections if s.get("script_text"))

        if not full_text.strip():
            full_text = (
                "MedSync AI — Collaborative Multi-Agent Emergency Response Platform. "
                "A critical incident has been successfully coordinated by five specialized AI agents. "
                "The action plan has been generated, validated, and approved. "
                "MedSync AI delivers faster, smarter, and audit-ready emergency coordination."
            )

        output_path = os.path.join(_AUDIO_DIR, f"voiceover_{incident_id}.mp3")

        try:
            if self.voice_provider == "edge_tts":
                audio_path = await self._generate_edge_tts(full_text, output_path)
            elif self.voice_provider == "elevenlabs":
                audio_path = await self._generate_elevenlabs(full_text, output_path)
            else:
                audio_path = await self._generate_gtts(full_text, output_path)

            logger.info("[VoiceoverAgent] Audio saved: %s", audio_path)
            return self._build_result(audio_path, self.voice_provider, full_text, sections, script)

        except Exception as exc:
            logger.warning("[VoiceoverAgent] Primary provider failed (%s): %s — trying gTTS", self.voice_provider, exc)
            # Fallback chain: edge_tts → gtts → silent
            try:
                audio_path = await self._generate_gtts(full_text, output_path)
                logger.info("[VoiceoverAgent] gTTS fallback succeeded")
                return self._build_result(audio_path, "gtts_fallback", full_text, sections, script)
            except Exception as exc2:
                logger.error("[VoiceoverAgent] gTTS fallback also failed: %s", exc2)
                silent_path = self._create_silent_placeholder(output_path)
                return {
                    "audio_path": silent_path,
                    "provider": "silent_fallback",
                    "total_chars": len(full_text),
                    "estimated_duration_sec": script.get("estimated_duration_sec", 120),
                    "section_timings": [],
                    "error": f"All providers failed: {exc2}",
                }

    def _build_result(
        self,
        audio_path: str,
        provider: str,
        full_text: str,
        sections: List[Dict],
        script: Dict,
    ) -> Dict:
        """Build the standard VoiceoverAgent result dict."""
        return {
            "audio_path": audio_path,
            "provider": provider,
            "total_chars": len(full_text),
            "estimated_duration_sec": int(len(full_text.split()) / 130 * 60),
            "section_timings": [
                {
                    "section_id": s.get("section_id"),
                    "duration_sec": int(s.get("duration_sec", 15)),  # cast to int — guard against numpy
                    "start_sec": int(sum(
                        sections[i].get("duration_sec", 15) for i in range(idx)
                    )),
                }
                for idx, s in enumerate(sections)
            ],
        }

    # ── Edge TTS (Microsoft Neural Voice — Free, No API Key) ─────────────────

    async def _generate_edge_tts(self, text: str, output_path: str) -> str:
        """
        Generate audio using Microsoft Edge TTS — neural quality, free, async.

        Package: edge-tts (pip install edge-tts)
        Voices: https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support
        """
        try:
            import edge_tts
        except ImportError:
            raise ImportError(
                "edge-tts not installed. Run: pip install edge-tts\n"
                "Alternatively set voice_provider='gtts' for the free fallback."
            )

        voice = _DEFAULT_EDGE_VOICE
        communicate = edge_tts.Communicate(text, voice)

        # Write to a temp .mp3 path then rename (atomic)
        tmp_path = output_path + ".tmp.mp3"
        try:
            await communicate.save(tmp_path)
            os.replace(tmp_path, output_path)
        except Exception as e:
            # Try fallback voices if primary fails
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            for fallback_voice in _FALLBACK_EDGE_VOICES:
                try:
                    logger.info("[VoiceoverAgent] Trying fallback voice: %s", fallback_voice)
                    communicate = edge_tts.Communicate(text, fallback_voice)
                    await communicate.save(tmp_path)
                    os.replace(tmp_path, output_path)
                    logger.info("[VoiceoverAgent] Edge TTS fallback voice succeeded: %s", fallback_voice)
                    return output_path
                except Exception:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    continue
            raise e  # All voices failed

        return output_path

    # ── gTTS (Google TTS — Free, Robotic) ────────────────────────────────────

    async def _generate_gtts(self, text: str, output_path: str) -> str:
        """Generate audio using Google Text-to-Speech (gTTS, free, no API key)."""
        import asyncio
        try:
            from gtts import gTTS
        except ImportError:
            raise ImportError("gTTS not installed. Run: pip install gTTS")

        def _sync_generate():
            tts = gTTS(text=text, lang="en", slow=False, tld="com")
            tts.save(output_path)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_generate)
        return output_path

    # ── ElevenLabs (Premium) ─────────────────────────────────────────────────

    async def _generate_elevenlabs(self, text: str, output_path: str) -> str:
        """Generate audio using ElevenLabs API (requires ELEVENLABS_API_KEY env var)."""
        import httpx

        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        if not api_key:
            logger.warning("[VoiceoverAgent] No ELEVENLABS_API_KEY — falling back to Edge TTS")
            return await self._generate_edge_tts(text, output_path)

        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "text": text[:5000],
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
            )
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(resp.content)

        return output_path

    # ── Silent Placeholder ───────────────────────────────────────────────────

    def _create_silent_placeholder(self, output_path: str) -> str:
        """Create a minimal silent MP3 file as last-resort fallback."""
        silent_mp3 = bytes([
            0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ])
        try:
            with open(output_path, "wb") as f:
                f.write(silent_mp3 * 100)
        except Exception:
            pass
        return output_path
