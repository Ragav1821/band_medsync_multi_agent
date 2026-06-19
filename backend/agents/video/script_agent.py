"""
Phase 20 — Script Agent
Converts the StorySchema narrative into a timed voice-over script.
"""
from __future__ import annotations

import logging
from typing import Dict, List

from services.gemini_service import get_gemini_service

logger = logging.getLogger(__name__)


class ScriptAgent:
    """
    Input : StorySchema (from StorytellingAgent)
    Output: ScriptSchema — timed voice-over script sections
    """

    SYSTEM = (
        "You are a professional documentary scriptwriter specializing in corporate and "
        "medical communications. You write voice-over scripts that are clear, authoritative, "
        "and engaging for executives. Sentences are short, punchy, and free of jargon. "
        "Pace the script for a natural speaking rate of 130 words per minute."
    )

    async def run(self, story: Dict, target_duration_sec: int = 120) -> Dict:
        logger.info("[ScriptAgent] Converting story to script. Target: %ds", target_duration_sec)

        prompt = self._build_prompt(story, target_duration_sec)
        gemini = get_gemini_service()
        result = await gemini.generate_json(
            prompt=prompt,
            system_instruction=self.SYSTEM,
            temperature=0.3,
            fallback=self._fallback_script(story, target_duration_sec),
        )
        result.setdefault("total_words", 0)
        result.setdefault("estimated_duration_sec", target_duration_sec)
        result.setdefault("sections", [])
        result.setdefault("title", story.get("title", "MedSync AI Executive Briefing"))
        logger.info("[ScriptAgent] Script with %d sections, ~%ds", len(result.get("sections", [])), result.get("estimated_duration_sec", 0))
        return result

    def _build_prompt(self, story: Dict, target_duration_sec: int) -> str:
        sections_text = "\n".join(
            f"- {s['section_id']}: {s['narrative']}"
            for s in story.get("sections", [])
        )
        target_words = int(target_duration_sec * 130 / 60)

        return f"""
Convert this executive story into a polished voice-over script for a {target_duration_sec}-second video.

STORY TITLE: {story.get('title', '')}
HOOK: {story.get('hook', '')}

STORY SECTIONS:
{sections_text}

BUSINESS IMPACT:
{story.get('business_impact', {})}

REQUIREMENTS:
- Target: {target_words} words total (~{target_duration_sec} seconds at 130 wpm)
- Tone: Executive, authoritative, inspiring — NOT robotic
- Each section: 2-5 sentences, no bullet points in the final script
- Include the hook as the opening
- End with a strong call-to-action about MedSync AI

Return this JSON schema EXACTLY:
{{
  "title": "{story.get('title', '')}",
  "total_words": <integer>,
  "estimated_duration_sec": <integer>,
  "sections": [
    {{
      "section_id": "intro",
      "title": "Opening",
      "script_text": "The exact words for the voice artist to read",
      "duration_sec": <integer, based on word count / 130 * 60>,
      "scene_hint": "Brief visual description for this section"
    }},
    {{
      "section_id": "problem",
      "title": "The Crisis",
      "script_text": "...",
      "duration_sec": <integer>,
      "scene_hint": "..."
    }},
    {{
      "section_id": "activation",
      "title": "AI Activation",
      "script_text": "...",
      "duration_sec": <integer>,
      "scene_hint": "..."
    }},
    {{
      "section_id": "collaboration",
      "title": "Agent Collaboration",
      "script_text": "...",
      "duration_sec": <integer>,
      "scene_hint": "..."
    }},
    {{
      "section_id": "negotiation",
      "title": "Intelligent Negotiation",
      "script_text": "...",
      "duration_sec": <integer>,
      "scene_hint": "..."
    }},
    {{
      "section_id": "action_plan",
      "title": "The Action Plan",
      "script_text": "...",
      "duration_sec": <integer>,
      "scene_hint": "..."
    }},
    {{
      "section_id": "outcome",
      "title": "Executive Outcome",
      "script_text": "...",
      "duration_sec": <integer>,
      "scene_hint": "..."
    }},
    {{
      "section_id": "cta",
      "title": "MedSync AI",
      "script_text": "MedSync AI. Where multi-agent intelligence meets human-centered care. The future of emergency coordination is here.",
      "duration_sec": 8,
      "scene_hint": "MedSync AI logo, dark background, subtle heartbeat animation"
    }}
  ]
}}

Return ONLY the JSON. No markdown, no explanation.
"""

    def _fallback_script(self, story: Dict, target_sec: int) -> Dict:
        sections = story.get("sections", [])
        per_section_sec = max(10, (target_sec - 20) // max(len(sections), 1))
        script_sections: List[Dict] = [
            {
                "section_id": "intro",
                "title": "Opening",
                "script_text": story.get("hook", "An emergency. A system. An answer."),
                "duration_sec": 12,
                "scene_hint": "MedSync AI title card over dark hospital background",
            }
        ]
        for s in sections:
            script_sections.append({
                "section_id": s.get("section_id", "section"),
                "title": s.get("title", ""),
                "script_text": s.get("narrative", ""),
                "duration_sec": per_section_sec,
                "scene_hint": s.get("key_stat", ""),
            })
        script_sections.append({
            "section_id": "cta",
            "title": "MedSync AI",
            "script_text": "MedSync AI. Where multi-agent intelligence meets human-centered care. The future of emergency coordination is here.",
            "duration_sec": 8,
            "scene_hint": "MedSync AI logo with heartbeat line",
        })
        total_words = sum(len(s["script_text"].split()) for s in script_sections)
        return {
            "title": story.get("title", "MedSync AI Executive Briefing"),
            "total_words": total_words,
            "estimated_duration_sec": int(total_words / 130 * 60),
            "sections": script_sections,
        }
