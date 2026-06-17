"""
Agent Base Class — all specialist agents inherit from this.
"""
import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional

from shared.context_store import context_store
from shared.event_bus import emit_agent_started, emit_agent_thinking, emit_agent_completed

logger = logging.getLogger(__name__)


class AgentBase(ABC):
    """
    Abstract base class for all MedSync AI specialist agents.
    Provides standard interface, logging, context sharing, and event emission.
    """

    agent_name: str = "base_agent"
    agent_role: str = "Base Agent"
    agent_description: str = "Base agent description"

    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.run_id = str(uuid.uuid4())
        self.status = "idle"
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.confidence_score: float = 0.0
        self.reasoning_trace: List[Dict] = []
        self.output: Optional[Dict] = None

    def _add_reasoning_step(self, step: str, content: str, data: Any = None):
        """Log a reasoning step for transparency and audit."""
        self.reasoning_trace.append({
            "step": step,
            "content": content,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _emit_thinking(self, step: str, content: str):
        """Broadcast a thinking step to connected clients."""
        self._add_reasoning_step(step, content)
        await emit_agent_thinking(self.incident_id, self.agent_name, step, content)
        await asyncio.sleep(0.3)  # Simulate processing time for demo

    # ------------------------------------------------------------------
    # LLM Bridge
    # ------------------------------------------------------------------
    async def _call_llm(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        fallback: Optional[Dict] = None,
        temperature: float = 0.1,
    ) -> Dict:
        """
        Call GeminiService and return a structured JSON dict.

        Behaviour
        ---------
        * Delegates to GeminiService.generate_json() which handles:
            - SIMULATION_MODE: returns deterministic fallback immediately.
            - Retry logic: up to 3 attempts with exponential back-off.
            - Timeout: controlled by GEMINI_TIMEOUT setting.
        * On *any* remaining exception this method logs and returns
          the provided *fallback* dict (or a generic safe structure)
          so the calling agent is never blocked.

        Parameters
        ----------
        prompt:             The full user prompt to send to Gemini.
        system_instruction: Optional system-level instruction.
        fallback:           Dict to return when Gemini is unavailable.
        temperature:        Gemini temperature (0.1 for structured output).

        Returns
        -------
        Parsed JSON dict — never raises.
        """
        # Import here to avoid circular deps and to surface install errors only at call time.
        try:
            from services.gemini_service import get_gemini_service
            service = get_gemini_service()
        except ImportError as exc:
            logger.error(
                "[%s] _call_llm: google-genai not installed → using fallback. %s",
                self.agent_name, exc,
            )
            return fallback or self._default_llm_fallback()

        safe_fallback = fallback or self._default_llm_fallback()

        try:
            result = await service.generate_json(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                fallback=safe_fallback,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[%s] _call_llm: unexpected error → fallback. %s",
                self.agent_name, exc,
            )
            return safe_fallback

    @staticmethod
    def _default_llm_fallback() -> Dict:
        """Generic safe structure returned when no caller-supplied fallback is given."""
        return {
            "simulation_mode": True,
            "summary": "LLM synthesis unavailable — using rule-based analysis.",
            "findings": [],
            "recommendations": [],
            "flags": [],
            "confidence_score": 0.70,
        }

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------
    async def run(self, incident_data: Dict) -> Dict:
        """
        Main entry point. Wraps the agent's analyze() method with
        standard logging, timing, context storage, and error handling.
        """
        self.started_at = datetime.utcnow()
        self.status = "active"

        await emit_agent_started(self.incident_id, self.agent_name)
        await self._emit_thinking("INIT", f"{self.agent_role} activated. Analyzing incident data...")

        try:
            result = await self.analyze(incident_data)
            self.output = result
            self.status = "completed"
            self.completed_at = datetime.utcnow()
            duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)

            # Write output to shared context store so other agents can read it
            await context_store.set_agent_output(self.incident_id, self.agent_name, result)

            await emit_agent_completed(
                self.incident_id,
                self.agent_name,
                result,
                result.get("confidence_score", 0.0),
            )

            return {
                "agent_name": self.agent_name,
                "run_id": self.run_id,
                "status": "completed",
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat(),
                "duration_ms": duration_ms,
                "confidence_score": result.get("confidence_score", 0.0),
                "output": result,
                "reasoning_trace": self.reasoning_trace,
            }

        except Exception as e:
            self.status = "error"
            self.completed_at = datetime.utcnow()
            return {
                "agent_name": self.agent_name,
                "run_id": self.run_id,
                "status": "error",
                "error": str(e),
                "reasoning_trace": self.reasoning_trace,
            }

    @abstractmethod
    async def analyze(self, incident_data: Dict) -> Dict:
        """
        Core analysis logic — implemented by each specialist agent.
        Must return a dict with at minimum:
          - summary: str
          - findings: List[str]
          - recommendations: List[str]
          - flags: List[str]
          - confidence_score: float
        """
        pass
