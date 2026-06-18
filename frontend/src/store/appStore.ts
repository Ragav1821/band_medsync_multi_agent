import { create } from 'zustand'
import type { Incident, ActionPlan, AgentRun, DashboardMetrics, AuditEvent } from '../api/client'
import { authApi } from '../api/client'

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
  band_chat_id?: string
  band_chat_url?: string
  // Phase 18: inter-agent message fields
  sender?: string
  receiver?: string
  message_type?: string
  metadata?: Record<string, unknown>
}

// Phase 18 — Typed inter-agent message
export interface AgentMessage {
  id?: string
  incident_id: string
  sender: string
  receiver: string
  message_type: string
  content: string
  metadata?: Record<string, unknown>
  timestamp?: string
}

// Phase 19 — Coordination Round tracking
export interface CoordinationRound {
  incident_id: string
  current_round: number
  max_rounds: number
  revision_count: number
  replan_count: number
  status: 'initial' | 'replanning' | 'approved' | 'rejected' | 'force_finalized'
  final_approval_round: number | null
  negotiation_log: Array<{ round: number; event: string; detail: string; timestamp: string }>
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

// ── Auth ──────────────────────────────────────────────────────────────────

export interface AuthUser {
  username: string
  name: string
  role: string
  display_name: string
  token: string
}

// ── Store ─────────────────────────────────────────────────────────────────

interface AppStore {
  // Auth (P0-2 / P0-3)
  currentUser: AuthUser | null
  authLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  restoreAuth: () => void

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

  // Band room — per incident
  bandRooms: Record<string, string>   // incident_id → band_chat_id
  setBandRoom: (incidentId: string, chatId: string) => void

  // Phase 18 — Agent messages (collaboration)
  agentMessages: Record<string, AgentMessage[]>  // incident_id → messages
  addAgentMessage: (msg: AgentMessage) => void
  clearAgentMessages: (incidentId: string) => void

  // Phase 19 — Coordination round tracking
  coordinationRounds: Record<string, CoordinationRound>  // incident_id → round
  setCoordinationRound: (incidentId: string, round: CoordinationRound) => void
}

export const useStore = create<AppStore>((set, get) => ({
  // ── Auth ────────────────────────────────────────────────────────────────
  currentUser: null,
  authLoading: false,

  login: async (username: string, password: string) => {
    set({ authLoading: true })
    try {
      const res = await authApi.login(username, password)
      const user: AuthUser = {
        username,
        name: res.data.user_name,
        role: res.data.role,
        display_name: res.data.display_name,
        token: res.data.access_token,
      }
      // Persist token so it survives page refresh
      localStorage.setItem('medsync_token', res.data.access_token)
      localStorage.setItem('medsync_user', JSON.stringify(user))
      set({ currentUser: user, authLoading: false })
    } catch (err: any) {
      set({ authLoading: false })
      throw new Error(err?.response?.data?.detail || 'Login failed')
    }
  },

  logout: () => {
    localStorage.removeItem('medsync_token')
    localStorage.removeItem('medsync_user')
    set({ currentUser: null })
  },

  restoreAuth: () => {
    try {
      const stored = localStorage.getItem('medsync_user')
      if (stored) set({ currentUser: JSON.parse(stored) })
    } catch {
      // corrupted storage — ignore
    }
  },

  // ── Incidents ────────────────────────────────────────────────────────────
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

    // ── Band room creation event ─────────────────────────────────────────────────
    if (event_type === 'band:room_created' && incident_id && event.band_chat_id) {
      get().setBandRoom(incident_id, event.band_chat_id)
      get().addFeedEvent(event)
      get().addToast({
        type: 'info',
        title: '📡 Band Room Active',
        message: `Coordination room created for incident ${incident_id.slice(0, 6).toUpperCase()}`,
      })
      return
    }

    // ── Phase 18: Agent → Agent message ─────────────────────────────────────────
    if (event_type === 'agent:message' && incident_id && event.sender && event.receiver) {
      get().addAgentMessage({
        incident_id,
        sender: event.sender!,
        receiver: event.receiver!,
        message_type: event.message_type || 'unknown',
        content: event.content || '',
        metadata: event.metadata,
        timestamp: event.timestamp,
      })
      get().addFeedEvent(event)  // also surface in live feed tab
      // Phase 19: show special toast for negotiation events
      if (event.message_type === 'revision_request') {
        get().addToast({
          type: 'warning',
          title: '🔄 Revision Requested',
          message: 'Compliance Agent requested a replan cycle.',
        })
      } else if (event.message_type === 'replan_request') {
        get().addToast({
          type: 'info',
          title: '♻️ Replanning',
          message: 'Commander initiated replan — agents revising plans.',
        })
      }
      return
    }

    // ── Phase 19A: Specific negotiation lifecycle events ────────────────
    if (event_type === 'negotiation:revision_requested' && incident_id) {
      get().addFeedEvent(event)
      get().addToast({
        type: 'warning',
        title: '🔄 Compliance Revision Requested',
        message: (event as any).message || 'Compliance flagged issues — requesting agent revision.',
      })
      return
    }
    if (event_type === 'negotiation:replanning_started' && incident_id) {
      get().addFeedEvent(event)
      get().addToast({
        type: 'info',
        title: '🔁 Replan Cycle Started',
        message: (event as any).message || 'Agents are revising their plans.',
      })
      return
    }
    if (event_type === 'negotiation:reapproved' && incident_id) {
      get().addFeedEvent(event)
      get().addToast({
        type: 'success',
        title: '✅ Plan Re-Approved',
        message: (event as any).message || 'Compliance approved the revised plan.',
      })
      return
    }
    if (event_type === 'negotiation:completed' && incident_id) {
      get().addFeedEvent(event)
      const finalStatus = (event as any).final_status
      get().addToast({
        type: finalStatus === 'approved' ? 'success' : 'warning',
        title: finalStatus === 'approved' ? '✅ Negotiation Complete' : '⚠️ Negotiation Force-Finalized',
        message: (event as any).message || 'Negotiation loop has completed.',
      })
      return
    }

    // ── Phase 19: Negotiation round update ──────────────────────────────
    if (event_type === 'negotiation:round_update' && incident_id && (event as any).coordination_round) {
      get().setCoordinationRound(incident_id, (event as any).coordination_round)
      get().addFeedEvent(event)
      return
    }

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

  // Band rooms
  bandRooms: {},
  setBandRoom: (incidentId, chatId) =>
    set((s) => ({ bandRooms: { ...s.bandRooms, [incidentId]: chatId } })),

  // Phase 18 — Agent messages
  agentMessages: {},
  addAgentMessage: (msg) =>
    set((s) => ({
      agentMessages: {
        ...s.agentMessages,
        [msg.incident_id]: [
          ...(s.agentMessages[msg.incident_id] ?? []),
          msg,
        ],
      },
    })),
  clearAgentMessages: (incidentId) =>
    set((s) => ({
      agentMessages: { ...s.agentMessages, [incidentId]: [] },
    })),

  // Phase 19 — Coordination rounds
  coordinationRounds: {},
  setCoordinationRound: (incidentId, round) =>
    set((s) => ({
      coordinationRounds: { ...s.coordinationRounds, [incidentId]: round },
    })),
}))
