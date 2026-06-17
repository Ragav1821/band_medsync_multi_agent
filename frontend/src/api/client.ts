// API client with auto base URL detection
import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

// ── Types ──────────────────────────────────────────────────────────────────

export interface Incident {
  id: string
  incident_type: string
  severity_level: number
  status: string
  incoming_patients: number
  icu_occupancy_pct: number
  ed_occupancy_pct: number
  available_nurses: number
  available_ventilators: number
  available_icu_beds: number
  total_icu_beds: number
  blood_bank_units: number
  reported_by: string
  created_at: string
  resolved_at?: string
}

export interface AgentRun {
  id: string
  incident_id: string
  agent_name: string
  status: string
  started_at?: string
  completed_at?: string
  duration_ms?: number
  confidence_score?: number
  output_data?: AgentOutput
  reasoning_trace?: ReasoningStep[]
}

export interface AgentOutput {
  agent_name: string
  summary: string
  findings: string[]
  recommendations: string[]
  flags: string[]
  confidence_score: number
  data?: Record<string, unknown>
}

export interface ReasoningStep {
  step: string
  content: string
  timestamp: string
}

export interface ActionItem {
  id: string
  description: string
  responsible_party: string
  timeline: string
  status: string
  is_compliant: boolean
  compliance_note?: string
}

export interface ExecutiveSummary {
  executive_summary: string
  critical_risks: string[]
  action_plan: Array<{ priority: number; action: string; owner: string; eta: string }>
  ai_generated: boolean
  simulation_mode?: boolean
}

export interface ActionPlan {
  id: string
  incident_id: string
  status: string
  severity_level: number
  severity_label: string
  priority_1_actions: ActionItem[]
  priority_2_actions: ActionItem[]
  priority_3_actions: ActionItem[]
  escalation_items: string[]
  compliance_status: string
  overall_summary: string
  required_documentation: string[]
  agent_outputs: Record<string, AgentOutput>
  executive_summary?: ExecutiveSummary
  approved_by?: string
  approved_at?: string
  created_at: string
}

export interface DashboardMetrics {
  total_incidents_today: number
  active_incidents: number
  resolved_incidents: number
  critical_incidents: number
  avg_response_time_minutes: number
  agent_runs_today: number
  compliance_rate_pct: number
  capacity_alerts: number
}

export interface SimulationScenario {
  id: string
  name: string
  description: string
  severity_label: string
  tags: string[]
}

export interface AuditEvent {
  id: string
  incident_id: string
  event_type: string
  actor_type: string
  actor_id: string
  event_data: Record<string, unknown>
  created_at: string
}

// ── API Methods ──────────────────────────────────────────────────────────────

export const incidentsApi = {
  list: () => api.get<Incident[]>('/incidents'),
  get: (id: string) => api.get<Incident>(`/incidents/${id}`),
  create: (data: Record<string, unknown>) => api.post('/incidents', data),
  resolve: (id: string) => api.patch(`/incidents/${id}/resolve`),
}

export const agentsApi = {
  getRuns: (incidentId: string) => api.get<AgentRun[]>(`/incidents/${incidentId}/agent-runs`),
}

export const actionPlanApi = {
  get: (incidentId: string) => api.get<ActionPlan>(`/incidents/${incidentId}/action-plan`),
  approve: (planId: string, approvedBy: string) =>
    api.patch(`/action-plans/${planId}/approve`, null, { params: { approved_by: approvedBy } }),
}

export const dashboardApi = {
  getMetrics: () => api.get<DashboardMetrics>('/dashboard/metrics'),
}

export const simulationApi = {
  list: () => api.get<SimulationScenario[]>('/simulation/scenarios'),
  run: (scenarioId: string) => api.post(`/simulation/run/${scenarioId}`),
}

export const auditApi = {
  list: (incidentId?: string) =>
    api.get<AuditEvent[]>('/audit-events', { params: incidentId ? { incident_id: incidentId } : {} }),
}
