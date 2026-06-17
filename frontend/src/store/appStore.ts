import { create } from 'zustand'
import type { Incident, ActionPlan, AgentRun, DashboardMetrics, AuditEvent } from '../api/client'

// ── WebSocket Event Types ─────────────────────────────────────────────────

export interface WSAgentEvent {
  event_type: string
  incident_id: string
  agent_name?: string
  step?: string
  content?: string
  output_summary?: string
  confidence?: number
  flags?: string[]
  action_plan_id?: string
  summary?: string
  level?: string
  message?: string
  plan_id?: string
  approved_by?: string
  timestamp?: string
}

// ── Toast ─────────────────────────────────────────────────────────────────

export interface Toast {
  id: string
  type: 'critical' | 'warning' | 'success' | 'info'
  title: string
  message: string
}

// ── Agent Live State ──────────────────────────────────────────────────────

export interface AgentLiveState {
  name: string
  status: 'idle' | 'active' | 'thinking' | 'completed' | 'error'
  currentStep?: string
  stepContent?: string
  confidence?: number
  progress: number
  flags: string[]
  summary?: string
}

const INITIAL_AGENTS: AgentLiveState[] = [
  { name: 'incident_commander', status: 'idle', progress: 0, flags: [] },
  { name: 'capacity_agent', status: 'idle', progress: 0, flags: [] },
  { name: 'staffing_agent', status: 'idle', progress: 0, flags: [] },
  { name: 'resource_agent', status: 'idle', progress: 0, flags: [] },
  { name: 'compliance_agent', status: 'idle', progress: 0, flags: [] },
]

// ── Store ─────────────────────────────────────────────────────────────────

interface AppStore {
  // Incidents
  incidents: Incident[]
  selectedIncidentId: string | null
  setIncidents: (incidents: Incident[]) => void
  addIncident: (incident: Incident) => void
  selectIncident: (id: string | null) => void

  // Metrics
  metrics: DashboardMetrics | null
  setMetrics: (m: DashboardMetrics) => void

  // Action Plans
  actionPlans: Record<string, ActionPlan>
  setActionPlan: (incidentId: string, plan: ActionPlan) => void

  // Agent live states
  agentStates: Record<string, AgentLiveState[]>
  handleWSEvent: (event: WSAgentEvent) => void
  resetAgents: (incidentId: string) => void

  // Activity feed
  feedEvents: WSAgentEvent[]
  addFeedEvent: (event: WSAgentEvent) => void

  // Agent runs
  agentRuns: Record<string, AgentRun[]>
  setAgentRuns: (incidentId: string, runs: AgentRun[]) => void

  // Toasts
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void

  // Audit
  auditEvents: AuditEvent[]
  setAuditEvents: (events: AuditEvent[]) => void

  // WS
  wsConnected: boolean
  setWsConnected: (v: boolean) => void
}

export const useStore = create<AppStore>((set, get) => ({
  incidents: [],
  selectedIncidentId: null,
  setIncidents: (incidents) => set({ incidents }),
  addIncident: (incident) => set((s) => ({ incidents: [incident, ...s.incidents] })),
  selectIncident: (id) => {
    set({ selectedIncidentId: id })
    if (id) get().resetAgents(id)
  },

  metrics: null,
  setMetrics: (metrics) => set({ metrics }),

  actionPlans: {},
  setActionPlan: (incidentId, plan) =>
    set((s) => ({ actionPlans: { ...s.actionPlans, [incidentId]: plan } })),

  agentStates: {},
  resetAgents: (incidentId) =>
    set((s) => ({
      agentStates: {
        ...s.agentStates,
        [incidentId]: INITIAL_AGENTS.map((a) => ({ ...a })),
      },
    })),

  handleWSEvent: (event) => {
    const { incident_id, agent_name, event_type } = event
    if (!incident_id || !agent_name) {
      // Global events (plan:ready, escalation, etc.)
      if (event_type === 'plan:ready') {
        get().addFeedEvent(event)
        get().addToast({ type: 'success', title: '✅ Action Plan Ready', message: event.summary || 'The Incident Commander has generated the final action plan.' })
      }
      if (event_type === 'alert:escalation') {
        get().addFeedEvent(event)
        get().addToast({ type: 'critical', title: '🚨 Escalation Required', message: event.message || 'Immediate executive action required.' })
      }
      return
    }

    get().addFeedEvent(event)

    set((s) => {
      const current = s.agentStates[incident_id] ?? INITIAL_AGENTS.map((a) => ({ ...a }))
      const updated = current.map((a) => {
        if (a.name !== agent_name) return a
        if (event_type === 'agent:started') {
          return { ...a, status: 'active' as const, progress: 10 }
        }
        if (event_type === 'agent:thinking') {
          return {
            ...a,
            status: 'thinking' as const,
            currentStep: event.step,
            stepContent: event.content,
            progress: Math.min(90, a.progress + 15),
          }
        }
        if (event_type === 'agent:completed') {
          return {
            ...a,
            status: 'completed' as const,
            progress: 100,
            confidence: event.confidence,
            flags: event.flags || [],
            summary: event.output_summary,
          }
        }
        if (event_type === 'agent:error') {
          return { ...a, status: 'error' as const, progress: 0 }
        }
        return a
      })
      return { agentStates: { ...s.agentStates, [incident_id]: updated } }
    })

    if (event_type === 'agent:completed') {
      const agentLabels: Record<string, string> = {
        capacity_agent: 'Capacity',
        staffing_agent: 'Staffing',
        resource_agent: 'Resource',
        compliance_agent: 'Compliance',
        incident_commander: 'Incident Commander',
      }
      get().addToast({
        type: 'info',
        title: `${agentLabels[agent_name] || agent_name} Agent Complete`,
        message: event.output_summary || 'Analysis complete.',
      })
    }
  },

  feedEvents: [],
  addFeedEvent: (event) =>
    set((s) => ({ feedEvents: [event, ...s.feedEvents].slice(0, 200) })),

  agentRuns: {},
  setAgentRuns: (incidentId, runs) =>
    set((s) => ({ agentRuns: { ...s.agentRuns, [incidentId]: runs } })),

  toasts: [],
  addToast: (toast) => {
    const id = Math.random().toString(36).slice(2)
    set((s) => ({ toasts: [...s.toasts, { ...toast, id }] }))
    setTimeout(() => get().removeToast(id), 6000)
  },
  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  auditEvents: [],
  setAuditEvents: (events) => set({ auditEvents: events }),

  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),
}))
