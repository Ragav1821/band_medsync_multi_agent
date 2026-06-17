import { useState } from 'react'
import { useStore } from '../store/appStore'
import { incidentsApi, simulationApi } from '../api/client'

const INCIDENT_TYPES = [
  { value: 'mass_casualty', label: '🚑 Mass Casualty Event' },
  { value: 'er_overload', label: '🏥 ED Overload' },
  { value: 'icu_saturation', label: '🫁 ICU Saturation' },
  { value: 'resource_shortage', label: '📦 Resource Shortage' },
  { value: 'staff_shortage', label: '👩‍⚕️ Staff Shortage' },
  { value: 'custom', label: '⚙️ Custom Incident' },
]

export function IncidentMonitor({ onNavigate }: { onNavigate: (page: string, id?: string) => void }) {
  const { incidents, setIncidents, addIncident, selectIncident, addToast } = useStore()
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formData, setFormData] = useState({
    incident_type: 'mass_casualty',
    incoming_patients: 50,
    icu_occupancy_pct: 92,
    ed_occupancy_pct: 78,
    available_nurses: 4,
    available_ventilators: 3,
    available_icu_beds: 2,
    total_icu_beds: 25,
    blood_bank_units: 30,
    reported_by: 'Operations Manager',
  })

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const res = await incidentsApi.create(formData)
      const incident = res.data.incident
      addIncident(incident)
      selectIncident(incident.id)
      setShowForm(false)
      addToast({ type: 'info', title: '🚨 Incident Created', message: `Multi-agent workflow activated for incident ${incident.id.slice(0, 8)}...` })
      onNavigate('agents', incident.id)
    } catch (err) {
      addToast({ type: 'warning', title: 'API Offline', message: 'Backend not running. Start backend with: cd backend && python main.py' })
    } finally {
      setSubmitting(false)
    }
  }

  const activeIncidents = incidents.filter(i => i.status !== 'resolved')
  const resolvedIncidents = incidents.filter(i => i.status === 'resolved')

  const severityLabel = (level: number) => {
    if (level === 3) return 'CRITICAL'
    if (level === 2) return 'MAJOR'
    return 'MINOR'
  }

  const statusLabel: Record<string, string> = {
    active: 'Active',
    agents_running: '🤖 Agents Running',
    plan_ready: '✅ Plan Ready',
    plan_approved: '✅ Approved',
    resolved: 'Resolved',
    escalated: '⬆️ Escalated',
  }

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 className="page-title">🚨 Incident Monitor</h1>
            <p className="page-subtitle">Create and manage emergency coordination incidents</p>
          </div>
          <button className="btn btn-critical" onClick={() => setShowForm(true)}>
            + New Incident
          </button>
        </div>
      </div>

      {/* Summary Badges */}
      <div style={{ display: 'flex', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-xl)', flexWrap: 'wrap' }}>
        <span className="badge badge-critical">{activeIncidents.filter(i => i.severity_level === 3).length} Critical</span>
        <span className="badge badge-warning">{activeIncidents.filter(i => i.severity_level === 2).length} Major</span>
        <span className="badge badge-accent">{activeIncidents.filter(i => i.severity_level === 1).length} Minor</span>
        <span className="badge badge-success">{resolvedIncidents.length} Resolved</span>
      </div>

      {/* Active Incidents */}
      <div className="section-header">
        <div className="section-title">Active Incidents ({activeIncidents.length})</div>
      </div>

      {activeIncidents.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon">✅</div>
          <div className="empty-state-title">No active incidents</div>
          <div className="empty-state-sub">All hospital systems operating normally</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
          {activeIncidents.map(incident => (
            <div key={incident.id} className="card" style={{ display: 'flex', gap: 'var(--spacing-lg)', alignItems: 'flex-start', cursor: 'pointer' }}
              onClick={() => { selectIncident(incident.id); onNavigate('agents', incident.id) }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className={`badge ${incident.severity_level === 3 ? 'badge-critical' : incident.severity_level === 2 ? 'badge-warning' : 'badge-success'}`}>
                    {severityLabel(incident.severity_level)}
                  </span>
                  <span style={{ color: 'white', fontWeight: 700, fontSize: '0.9rem' }}>
                    {INCIDENT_TYPES.find(t => t.value === incident.incident_type)?.label || incident.incident_type}
                  </span>
                  <span style={{ marginLeft: 'auto' }} className={`badge ${incident.status === 'plan_ready' || incident.status === 'plan_approved' ? 'badge-success' : 'badge-accent'}`}>
                    {statusLabel[incident.status] || incident.status}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 4 }}>
                  <Stat label="Incoming" value={incident.incoming_patients} unit="pts" />
                  <Stat label="ICU" value={`${incident.icu_occupancy_pct}%`} />
                  <Stat label="Nurses" value={incident.available_nurses} />
                  <Stat label="Ventilators" value={incident.available_ventilators} />
                </div>
                <div style={{ fontSize: '0.7rem', color: 'rgba(140,180,220,0.4)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                  ID: {incident.id.slice(0, 8)} · {new Date(incident.created_at).toLocaleTimeString()}
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); selectIncident(incident.id); onNavigate('action-plan', incident.id) }}>
                  View Plan
                </button>
                <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); selectIncident(incident.id); onNavigate('agents', incident.id) }}>
                  Agent Feed
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Incident Modal */}
      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-xl)' }}>
              <div>
                <h2 style={{ color: 'white', fontSize: '1.2rem', fontWeight: 800 }}>🚨 New Emergency Incident</h2>
                <p style={{ color: 'rgba(140,180,220,0.5)', fontSize: '0.82rem', marginTop: 4 }}>
                  Triggers the multi-agent coordination workflow
                </p>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>✕</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              <div className="form-group">
                <label className="form-label">Incident Type</label>
                <select className="form-control" value={formData.incident_type} onChange={e => setFormData(d => ({ ...d, incident_type: e.target.value }))}>
                  {INCIDENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Incoming Patients</label>
                  <input type="number" className="form-control" value={formData.incoming_patients}
                    onChange={e => setFormData(d => ({ ...d, incoming_patients: +e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">ICU Occupancy %</label>
                  <input type="number" className="form-control" value={formData.icu_occupancy_pct}
                    onChange={e => setFormData(d => ({ ...d, icu_occupancy_pct: +e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Available Nurses</label>
                  <input type="number" className="form-control" value={formData.available_nurses}
                    onChange={e => setFormData(d => ({ ...d, available_nurses: +e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Available Ventilators</label>
                  <input type="number" className="form-control" value={formData.available_ventilators}
                    onChange={e => setFormData(d => ({ ...d, available_ventilators: +e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Blood Bank Units</label>
                  <input type="number" className="form-control" value={formData.blood_bank_units}
                    onChange={e => setFormData(d => ({ ...d, blood_bank_units: +e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">ED Occupancy %</label>
                  <input type="number" className="form-control" value={formData.ed_occupancy_pct}
                    onChange={e => setFormData(d => ({ ...d, ed_occupancy_pct: +e.target.value }))} />
                </div>
              </div>

              {/* Severity Preview */}
              <div style={{ padding: 'var(--spacing-md)', borderRadius: 'var(--radius-md)', background: 'var(--color-critical-dim)', border: '1px solid rgba(255,59,92,0.2)' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--color-critical)', marginBottom: 4 }}>
                  Predicted Severity: LEVEL 3 — CRITICAL
                </div>
                <div style={{ fontSize: '0.72rem', color: 'rgba(255,100,120,0.7)' }}>
                  All 5 agents will be activated simultaneously. Executive notification will be dispatched.
                </div>
              </div>

              <div style={{ display: 'flex', gap: 'var(--spacing-sm)', justifyContent: 'flex-end', marginTop: 'var(--spacing-sm)' }}>
                <button className="btn btn-ghost" onClick={() => setShowForm(false)}>Cancel</button>
                <button className="btn btn-critical" onClick={handleSubmit} disabled={submitting}>
                  {submitting ? '⏳ Activating Agents...' : '🚨 Activate Multi-Agent Workflow'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, unit = '' }: { label: string; value: string | number; unit?: string }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', padding: '6px 10px' }}>
      <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.4)' }}>{label}</div>
      <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'white' }}>{value}{unit && <span style={{ fontSize: '0.7rem', opacity: 0.6 }}> {unit}</span>}</div>
    </div>
  )
}
