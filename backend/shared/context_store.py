"""
Shared In-Memory Context Store
Simulates Redis for the hackathon demo — replace with actual Redis in production.
"""
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


class InMemoryContextStore:
    """
    Shared context store for agent collaboration.
    Agents write their outputs here and can read other agents' outputs.
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._pubsub: Dict[str, List] = {}
        self._incident_state: Dict[str, Dict] = {}

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Write a value to the shared store."""
        self._store[key] = {
            "value": value,
            "written_at": datetime.utcnow().isoformat(),
            "ttl": ttl_seconds,
        }

    async def get(self, key: str) -> Optional[Any]:
        """Read a value from the shared store."""
        entry = self._store.get(key)
        if entry:
            return entry["value"]
        return None

    async def set_agent_output(self, incident_id: str, agent_name: str, output: Dict):
        """Store an agent's output for a specific incident."""
        key = f"incident:{incident_id}:agent:{agent_name}:output"
        await self.set(key, output)

    async def get_agent_output(self, incident_id: str, agent_name: str) -> Optional[Dict]:
        """Retrieve an agent's output for a specific incident."""
        key = f"incident:{incident_id}:agent:{agent_name}:output"
        return await self.get(key)

    async def get_all_agent_outputs(self, incident_id: str) -> Dict[str, Dict]:
        """Retrieve all agent outputs for an incident."""
        agents = ["capacity_agent", "staffing_agent", "resource_agent", "compliance_agent"]
        results = {}
        for agent in agents:
            output = await self.get_agent_output(incident_id, agent)
            if output:
                results[agent] = output
        return results

    async def set_incident_state(self, incident_id: str, state: Dict):
        """Update the current state of an incident."""
        self._incident_state[incident_id] = {
            **self._incident_state.get(incident_id, {}),
            **state,
            "updated_at": datetime.utcnow().isoformat(),
        }

    async def get_incident_state(self, incident_id: str) -> Dict:
        """Get the current state of an incident."""
        return self._incident_state.get(incident_id, {})

    async def publish(self, channel: str, message: Dict):
        """Publish a message to a channel (pub/sub simulation)."""
        if channel not in self._pubsub:
            self._pubsub[channel] = []
        self._pubsub[channel].append({
            **message,
            "published_at": datetime.utcnow().isoformat(),
        })

    async def clear_incident(self, incident_id: str):
        """Clear all data for an incident."""
        keys_to_delete = [k for k in self._store.keys() if incident_id in k]
        for key in keys_to_delete:
            del self._store[key]
        if incident_id in self._incident_state:
            del self._incident_state[incident_id]


# Singleton instance
context_store = InMemoryContextStore()
