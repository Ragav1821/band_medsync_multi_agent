import { useEffect, useState } from 'react'
import { useStore } from '../store/appStore'
import { dashboardApi, incidentsApi, type Incident } from '../api/client'
import { RadialBarChart, RadialBar, ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts'
import { BandRoomPanel } from '../components/band/BandRoomPanel'
import { CollaborationTimeline } from '../components/band/CollaborationTimeline'
import { BandMetricsCard } from '../components/band/BandMetricsCard'

function MetricCard({ title, value, sub, type = '' }: { title: string; value: string | number; sub: string; type?: string }) {
  return (
    <div className="card">
      <div className="card-title">{title}</div>
      <div className={`card-value ${type}`}>{value}</div>
      <div className="card-sub">{sub}</div>
    </div>
  )
}

function CapacityBar({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100)
  const level = pct >= 90 ? 'critical' : pct >= 70 ? 'warning' : 'safe'
  const color = level === 'critical' ? 'var(--color-critical)' : level === 'warning' ? 'var(--color-warning)' : 'var(--color-success)'
  return (
    <div className="capacity-item">
      <div className="capacity-label-row">
        <span className="capacity-label">{label}</span>
        <span className="capacity-value" style={{ color }}>{value.toFixed(0)}%</span>
      </div>
      <div className="capacity-bar">
        <div className={`capacity-fill ${level}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

const trendData = [
  { time: '00:00', incidents: 0 }, { time: '04:00', incidents: 1 },
  { time: '08:00', incidents: 2 }, { time: '10:00', incidents: 4 },
  { time: '12:00', incidents: 3 }, { time: '14:00', incidents: 5 },
  { time: '16:00', incidents: 4 }, { time: '18:00', incidents: 6 },
  { time: '20:00', incidents: 3 }, { time: '22:00', incidents: 2 },
]

export function Dashboard({ onNavigate }: { onNavigate: (page: string, id?: string) => void }) {
  const { metrics, setMetrics, incidents, setIncidents } = useStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [metricsRes, incidentsRes] = await Promise.all([
          dashboardApi.getMetrics(),
          incidentsApi.list(),
        ])
        setMetrics(metricsRes.data)
        setIncidents(incidentsRes.data)
      } catch (err) {
        console.warn('API not available, using demo data')
        setMetrics({
          total_incidents_today: 7,
          active_incidents: 2,
          resolved_incidents: 5,
          critical_incidents: 1,
          avg_response_time_minutes: 2.3,
          agent_runs_today: 35,
          compliance_rate_pct: 94.2,
          capacity_alerts: 1,
        })
      } finally {
        setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [setMetrics, setIncidents])

  const activeIncidents = incidents.filter(i => i.status !== 'resolved')
  const criticalIncidents = incidents.filter(i => i.severity_level === 3)

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 className="page-title">⚡ Command Center</h1>
            <p className="page-subtitle">Real-time hospital emergency operations overview</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('simulation')}>🧪 Run Simulation</button>
            <button className="btn btn-critical btn-sm" onClick={() => onNavigate('incidents')}>🚨 New Incident</button>
          </div>
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="metric-grid">
        <MetricCard title="Active Incidents" value={metrics?.active_incidents ?? '—'} sub="Requiring coordination" type={metrics && metrics.active_incidents > 0 ? 'critical' : 'success'} />
        <MetricCard title="Critical Level 3" value={metrics?.critical_incidents ?? '—'} sub="Mass casualty / critical" type={metrics && metrics.critical_incidents > 0 ? 'critical' : ''} />
        <MetricCard title="Avg Response" value={metrics ? `${metrics.avg_response_time_minutes}m` : '—'} sub="Agent plan generation time" type="accent" />
        <MetricCard title="Agent Runs Today" value={metrics?.agent_runs_today ?? '—'} sub="Multi-agent workflows" type="accent" />
        <MetricCard title="Compliance Rate" value={metrics ? `${metrics.compliance_rate_pct}%` : '—'} sub="Validated recommendations" type="success" />
        <MetricCard title="Resolved Today" value={metrics?.resolved_incidents ?? '—'} sub="Incidents closed" type="success" />
      </div>

      {/* Band Metrics Card — standalone reusable component */}
      <div style={{ marginBottom: 'var(--spacing-lg)' }}>
        <BandMetricsCard onNavigate={onNavigate} />
      </div>

      <div className="grid-2">
        {/* Capacity Overview */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">🏥 Capacity Overview</div>
            <span className="badge badge-warning">Live</span>
          </div>
          <div className="capacity-bar-group">
            <CapacityBar label="ICU Occupancy" value={92} />
            <CapacityBar label="Emergency Dept" value={78} />
            <CapacityBar label="General Wards" value={61} />
            <CapacityBar label="Operating Rooms" value={45} />
            <CapacityBar label="Step-Down Unit" value={83} />
          </div>
        </div>

        {/* Incident Trend */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">📈 Incident Trend (Today)</div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="incidentGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-accent)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" tick={{ fill: 'rgba(140,180,220,0.4)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'rgba(140,180,220,0.4)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'white', fontSize: 12 }}
                cursor={{ stroke: 'rgba(0,163,255,0.3)' }}
              />
              <Area type="monotone" dataKey="incidents" stroke="var(--color-accent)" strokeWidth={2} fill="url(#incidentGradient)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Active Incidents */}
      <div style={{ marginTop: 'var(--spacing-xl)' }}>
        <div className="section-header">
          <div>
            <div className="section-title">Active Incidents</div>
            <div className="section-subtitle">{activeIncidents.length} incidents requiring attention</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('incidents')}>View All →</button>
        </div>
        <div className="incident-list">
          {activeIncidents.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 32, color: 'rgba(140,180,220,0.4)' }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
              <div>No active incidents — all systems operational</div>
            </div>
          ) : (
            activeIncidents.slice(0, 5).map(incident => (
              <IncidentRow key={incident.id} incident={incident} onClick={() => onNavigate('action-plan', incident.id)} />
            ))
          )}
        </div>
      </div>

      {/* Band Room + Collaboration Timeline */}
      <div style={{ marginTop: 'var(--spacing-xl)' }}>
        <div className="section-header" style={{ marginBottom: 'var(--spacing-md)' }}>
          <div>
            <div className="section-title">📡 Live Band Coordination</div>
            <div className="section-subtitle">Real-time agent collaboration via Band room</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('agents')}>View Full Timeline →</button>
        </div>
        <div className="grid-2">
          <BandRoomPanel />
          <CollaborationTimeline />
        </div>
      </div>

      {/* Agent Status Summary */}
      <div style={{ marginTop: 'var(--spacing-xl)' }}>
        <div className="section-header">
          <div>
            <div className="section-title">AI Agent Fleet — Band Connected</div>
            <div className="section-subtitle">5 specialist agents coordinating through Band</div>
          </div>
        </div>
        <div className="agent-grid">
          {AGENT_INFO.map(agent => (
            <AgentStatusCard key={agent.name} agent={agent} />
          ))}
        </div>
      </div>
    </div>
  )
}

function IncidentRow({ incident, onClick }: { incident: Incident; onClick: () => void }) {
  const labels: Record<string, string> = {
    mass_casualty: 'Mass Casualty Event',
    er_overload: 'ED Overload',
    icu_saturation: 'ICU Saturation',
    resource_shortage: 'Resource Shortage',
    staff_shortage: 'Staff Shortage',
    custom: 'Custom Incident',
  }
  const statusColors: Record<string, string> = {
    active: 'badge-warning',
    agents_running: 'badge-accent',
    plan_ready: 'badge-success',
    plan_approved: 'badge-success',
    escalated: 'badge-critical',
  }

  return (
    <div className="incident-card" onClick={onClick}>
      <div className={`incident-severity-bar sev-${incident.severity_level}`} />
      <div className="incident-info">
        <div className="incident-title">{labels[incident.incident_type] || incident.incident_type}</div>
        <div className="incident-meta">
          {incident.incoming_patients} patients · ICU {incident.icu_occupancy_pct}% · {incident.available_nurses} nurses
        </div>
      </div>
      <span className={`badge ${statusColors[incident.status] || 'badge-info'}`}>
        {incident.status.replace('_', ' ').toUpperCase()}
      </span>
    </div>
  )
}

const AGENT_INFO = [
  { name: 'Incident Commander', role: 'Orchestration & Planning', icon: '🎯', className: 'commander' },
  { name: 'Capacity Agent', role: 'ICU & ED Load Analysis', icon: '🏥', className: 'capacity' },
  { name: 'Staffing Agent', role: 'Nurse Allocation & Gaps', icon: '👩‍⚕️', className: 'staffing' },
  { name: 'Resource Agent', role: 'Equipment & Supplies', icon: '📦', className: 'resource' },
  { name: 'Compliance Agent', role: 'EMTALA & Regulations', icon: '⚖️', className: 'compliance' },
]

function AgentStatusCard({ agent }: { agent: typeof AGENT_INFO[0] }) {
  return (
    <div className="agent-card">
      <div className="agent-card-header">
        <div className={`agent-icon ${agent.className}`} style={{ fontSize: '1.2rem' }}>{agent.icon}</div>
        <div>
          <div className="agent-name">{agent.name}</div>
          <div className="agent-role">{agent.role}</div>
        </div>
        <div className="agent-status completed" style={{ marginLeft: 'auto' }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
          Ready
        </div>
      </div>
    </div>
  )
}
