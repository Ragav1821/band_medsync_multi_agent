"""
GeminiService — Singleton async wrapper around Google Gemini 2.5 Flash.

Responsibilities
----------------
* Initialise the google-genai client once (singleton pattern).
* Provide async text generation with configurable timeout.
* Support optional JSON-mode responses.
* Retry transient network errors with exponential back-off (tenacity).
* Fall back to SIMULATION_MODE deterministic responses when:
    - SIMULATION_MODE=true in settings, OR
    - No GEMINI_API_KEY is configured, OR
    - All retry attempts are exhausted.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import — only fail at call time, not at import time.
# ---------------------------------------------------------------------------
_genai_available = False
try:
    from google import genai
    from google.genai import types as genai_types
    _genai_available = True
except ImportError:
    logger.warning(
        "google-genai package not installed. Install it via: "
        "pip install google-genai>=1.16.0. "
        "GeminiService will run in SIMULATION_MODE."
    )


# ---------------------------------------------------------------------------
# Sentinel — used to detect "not yet initialised"
# ---------------------------------------------------------------------------
_UNSET = object()


class GeminiService:
    """
    Async singleton wrapper around Gemini 2.5 Flash.

    Usage
    -----
    service = GeminiService.get_instance()
    result  = await service.generate(prompt="...")
    json_r  = await service.generate_json(prompt="...", schema={...})
    """

    _instance: Optional["GeminiService"] = None

    # ------------------------------------------------------------------
    # Singleton constructor
    # ------------------------------------------------------------------
    def __init__(self) -> None:
        self._client: Any = None          # google.genai.Client
        self._model: str = settings.gemini_model
        self._timeout: int = settings.gemini_timeout
        self._simulation_mode: bool = self._resolve_simulation_mode()
        self._initialised: bool = False

    @classmethod
    def get_instance(cls) -> "GeminiService":
        """Return (and lazily create) the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
            # Fire-and-forget — initialise on first call; errors are logged.
        return cls._instance

    # ------------------------------------------------------------------
    # Internal initialisation
    # ------------------------------------------------------------------
    def _resolve_simulation_mode(self) -> bool:
        """
        Simulation mode is active when:
        - settings.simulation_mode is explicitly True, OR
        - No Gemini API key is present, OR
        - google-genai is not installed.
        """
        if settings.simulation_mode:
            logger.info("GeminiService: SIMULATION_MODE=true (settings)")
            return True
        if not _genai_available:
            logger.warning("GeminiService: google-genai not installed → simulation mode")
            return True
        if not settings.gemini_api_key:
            logger.warning("GeminiService: GEMINI_API_KEY not set → simulation mode")
            return True
        return False

    def _ensure_client(self) -> None:
        """Lazily initialise the Gemini client (called once per service lifetime)."""
        if self._initialised:
            return
        self._initialised = True

        if self._simulation_mode:
            logger.info("GeminiService: running in simulation mode — client not created")
            return

        try:
            self._client = genai.Client(api_key=settings.gemini_api_key)
            logger.info(
                "GeminiService: Gemini client initialised (model=%s, timeout=%ss)",
                self._model,
                self._timeout,
            )
        except Exception as exc:
            logger.error("GeminiService: client init failed → simulation mode. Error: %s", exc)
            self._simulation_mode = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """
        Generate a text response for *prompt*.

        Returns the raw text string.
        Falls back to simulation string on any failure.
        """
        self._ensure_client()

        if self._simulation_mode:
            return self._simulation_fallback_text(prompt)

        try:
            return await self._call_with_retry(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                json_mode=False,
            )
        except Exception as exc:
            logger.error("GeminiService.generate: all retries exhausted → fallback. %s", exc)
            return self._simulation_fallback_text(prompt)

    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        fallback: Optional[Dict] = None,
    ) -> Dict:
        """
        Generate a structured JSON response for *prompt*.

        Returns a parsed Python dict.
        Falls back to *fallback* dict (or a safe default) on any failure.
        """
        self._ensure_client()

        if self._simulation_mode:
            return fallback or self._simulation_fallback_json(prompt)

        try:
            raw = await self._call_with_retry(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                json_mode=True,
            )
            return self._parse_json(raw, fallback or {})
        except Exception as exc:
            logger.error("GeminiService.generate_json: all retries exhausted → fallback. %s", exc)
            return fallback or self._simulation_fallback_json(prompt)

    @property
    def is_simulation(self) -> bool:
        """True when running without a live Gemini connection."""
        return self._simulation_mode

    # ------------------------------------------------------------------
    # Internal — retry-decorated call
    # ------------------------------------------------------------------
    async def _call_with_retry(
        self,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        json_mode: bool,
    ) -> str:
        """
        Run the actual Gemini API call, wrapped in tenacity retry logic.
        Retries up to 3 times on transient errors with exponential back-off.
        """

        @retry(
            retry=retry_if_exception_type((Exception,)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _attempt() -> str:
            return await asyncio.wait_for(
                self._raw_generate(prompt, system_instruction, temperature, json_mode),
                timeout=self._timeout,
            )

        return await _attempt()

    async def _raw_generate(
        self,
        prompt: str,
        system_instruction: Optional[str],
        temperature: float,
        json_mode: bool,
    ) -> str:
        """Execute a single Gemini API call (blocking IO wrapped in executor)."""

        def _sync_call() -> str:
            config_kwargs: Dict[str, Any] = {
                "temperature": temperature,
            }
            if json_mode:
                config_kwargs["response_mime_type"] = "application/json"

            generate_config = genai_types.GenerateContentConfig(
                **config_kwargs,
                **({"system_instruction": system_instruction} if system_instruction else {}),
            )

            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=generate_config,
            )
            return response.text

        # Run the synchronous SDK call in a thread so we don't block the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_call)

    # ------------------------------------------------------------------
    # Deterministic fallbacks (SIMULATION_MODE or total failure)
    # ------------------------------------------------------------------
    @staticmethod
    def _simulation_fallback_text(prompt: str) -> str:
        """Return a safe placeholder text that matches what the callers expect."""
        return (
            "[SIMULATION] Gemini AI is not connected. "
            "This response is deterministically generated for demo/testing purposes. "
            "All agent outputs above are based on rule-based analysis of the incident data."
        )

    @staticmethod
    def _simulation_fallback_json(prompt: str) -> Dict:
        """Return a safe placeholder JSON structure."""
        return {
            "simulation_mode": True,
            "note": "Gemini AI not available. Deterministic fallback response.",
            "summary": "AI synthesis unavailable — see rule-based agent outputs for analysis.",
            "critical_risks": [],
            "action_plan": [],
        }

    @staticmethod
    def _parse_json(raw: str, fallback: Dict) -> Dict:
        """Safely parse a JSON string returned by Gemini."""
        # Strip markdown fences if present (```json ... ```)
        stripped = raw.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            # Drop first (```json) and last (```) lines
            stripped = "\n".join(lines[1:-1]).strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            logger.warning("GeminiService: JSON parse failed (%s) → fallback", exc)
            return fallback


# ---------------------------------------------------------------------------
# Module-level convenience accessor
# ---------------------------------------------------------------------------
def get_gemini_service() -> GeminiService:
    """FastAPI-friendly dependency / direct accessor."""
    return GeminiService.get_instance()
