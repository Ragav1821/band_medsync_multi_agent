# MedSync AI 🏥⚡
## AI-Powered Multi-Agent Hospital Emergency Coordination Platform

> **Hackathon Track:** Internal Enterprise Workflows

---

## Quick Start

### Backend (FastAPI)
```bash
cd backend
pip install fastapi uvicorn pydantic pydantic-settings python-multipart
python main.py
# → API running at http://localhost:8000
# → Docs at http://localhost:8000/api/docs
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
# → UI running at http://localhost:5173
```

---

## Architecture Overview

```
MedSync AI Platform
├── 🎯 Incident Commander Agent  ← Master Orchestrator
├── 🏥 Capacity Agent           ← ICU/ED load analysis
├── 👩‍⚕️ Staffing Agent          ← Nurse allocation & gaps
├── 📦 Resource Agent           ← Equipment & supplies
└── ⚖️ Compliance Agent         ← EMTALA & regulations
```

## Workflow (Mass Casualty Event)

1. **Incident Created** → Commander classifies severity
2. **Parallel Dispatch** → Capacity + Staffing + Resource agents run simultaneously
3. **Context Sharing** → Agents read each other's outputs via shared store
4. **Compliance Validation** → Compliance agent validates all recommendations
5. **Action Plan** → Commander synthesizes Final Action Plan
6. **Human Approval** → Operations Manager reviews and approves with one click
7. **Notifications** → All departments notified automatically

## Key Features

- ✅ 5 specialized AI agents with distinct roles
- ✅ Parallel agent execution with shared context
- ✅ Real-time WebSocket streaming of agent activity
- ✅ Compliance validation against EMTALA & Joint Commission
- ✅ 5 pre-built simulation scenarios
- ✅ Immutable audit trail
- ✅ Human-in-the-loop approval flow
- ✅ Premium dark-mode UI

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/incidents | Create incident + trigger agents |
| GET | /api/v1/incidents | List all incidents |
| POST | /api/v1/simulation/run/{id} | Run simulation scenario |
| GET | /api/v1/incidents/{id}/action-plan | Get action plan |
| PATCH | /api/v1/action-plans/{id}/approve | Approve action plan |
| WS | /api/v1/ws/incidents/{id} | Real-time agent events |

## Simulation Scenarios

| ID | Scenario | Severity |
|----|----------|----------|
| sim_001 | Mass Casualty Event (50 patients) | CRITICAL |
| sim_002 | ED Overload (flu surge) | MAJOR |
| sim_003 | ICU Saturation (98%) | CRITICAL |
| sim_004 | Staff Shortage (40% out) | CRITICAL |
| sim_005 | Resource Shortage | MAJOR |

---

Built for the hackathon by MedSync AI Team
