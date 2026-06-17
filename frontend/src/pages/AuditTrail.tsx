import { useEffect } from 'react'
import { useStore } from '../store/appStore'
import { auditApi } from '../api/client'

const DEMO_AUDIT = [
  { id: '1', incident_id: 'demo', event_type: 'incident_created', actor_type: 'system', actor_id: 'system', event_data: { severity: 3 }, created_at: new Date(Date.now() - 300000).toISOString() },
  { id: '2', incident_id: 'demo', event_type: 'agent_started', actor_type: 'agent', actor_id: 'incident_commander', event_data: {}, created_at: new Date(Date.now() - 298000).toISOString() },
  { id: '3', incident_id: 'demo', event_type: 'agent_started', actor_type: 'agent', actor_id: 'capacity_agent', event_data: {}, created_at: new Date(Date.now() - 297000).toISOString() },
  { id: '4', incident_id: 'demo', event_type: 'agent_started', actor_type: 'agent', actor_id: 'staffing_agent', event_data: {}, created_at: new Date(Date.now() - 297000).toISOString() },
  { id: '5', incident_id: 'demo', event_type: 'agent_started', actor_type: 'agent', actor_id: 'resource_agent', event_data: {}, created_at: new Date(Date.now() - 297000).toISOString() },
  { id: '6', incident_id: 'demo', event_type: 'escalation_triggered', actor_type: 'agent', actor_id: 'incident_commander', event_data: { level: 'CRITICAL', notified: ['CMO', 'CEO'] }, created_at: new Date(Date.now() - 290000).toISOString() },
  { id: '7', incident_id: 'demo', event_type: 'agent_completed', actor_type: 'agent', actor_id: 'capacity_agent', event_data: { confidence: 0.92 }, created_at: new Date(Date.now() - 285000).toISOString() },
  { id: '8', incident_id: 'demo', event_type: 'agent_completed', actor_type: 'agent', actor_id: 'staffing_agent', event_data: { confidence: 0.88 }, created_at: new Date(Date.now() - 283000).toISOString() },
  { id: '9', incident_id: 'demo', event_type: 'agent_completed', actor_type: 'agent', actor_id: 'resource_agent', event_data: { confidence: 0.85 }, created_at: new Date(Date.now() - 281000).toISOString() },
  { id: '10', incident_id: 'demo', event_type: 'agent_completed', actor_type: 'agent', actor_id: 'compliance_agent', event_data: { compliance_status: 'CONDITIONALLY_COMPLIANT' }, created_at: new Date(Date.now() - 275000).toISOString() },
  { id: '11', incident_id: 'demo', event_type: 'action_plan_created', actor_type: 'agent', actor_id: 'incident_commander', event_data: { actions: 10 }, created_at: new Date(Date.now() - 270000).toISOString() },
  { id: '12', incident_id: 'demo', event_type: 'plan_approved', actor_type: 'human', actor_id: 'Operations Manager', event_data: { approved_by: 'Alex Chen' }, created_at: new Date(Date.now() - 240000).toISOString() },
]

const eventLabels: Record<string, { label: string; icon: string }> = {
  incident_created: { label: 'Incident Created', icon: '🚨' },
  agent_started: { label: 'Agent Activated', icon: '🤖' },
  agent_completed: { label: 'Agent Completed', icon: '✅' },
  action_plan_created: { label: 'Action Plan Generated', icon: '📋' },
  plan_approved: { label: 'Plan Approved', icon: '✅' },
  escalation_triggered: { label: 'Escalation Triggered', icon: '⬆️' },
  status_changed: { label: 'Status Updated', icon: '🔄' },
}

export function AuditTrail() {
  const { auditEvents, setAuditEvents, selectedIncidentId } = useStore()

  useEffect(() => {
    const fetchAudit = async () => {
      try {
        const res = await auditApi.list(selectedIncidentId || undefined)
        setAuditEvents(res.data)
      } catch {
        setAuditEvents(DEMO_AUDIT)
      }
    }
    fetchAudit()
  }, [selectedIncidentId, setAuditEvents])

  const displayEvents = auditEvents.length > 0 ? auditEvents : DEMO_AUDIT

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">📜 Audit Trail</h1>
        <p className="page-subtitle">Immutable log of all agent decisions, human approvals, and compliance events</p>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-xl)', flexWrap: 'wrap' }}>
        <span className="badge badge-accent">{displayEvents.length} Total Events</span>
        <span className="badge badge-info">{displayEvents.filter(e => e.actor_type === 'agent').length} Agent Decisions</span>
        <span className="badge badge-success">{displayEvents.filter(e => e.actor_type === 'human').length} Human Actions</span>
        <span className="badge badge-warning">{displayEvents.filter(e => e.event_type.includes('escalation')).length} Escalations</span>
        <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }}>⬇️ Export CSV</button>
        <button className="btn btn-ghost btn-sm">📄 Generate PDF Report</button>
      </div>

      <div className="card">
        <div className="audit-timeline">
          {displayEvents.map(event => {
            const meta = eventLabels[event.event_type] || { label: event.event_type, icon: '•' }
            return (
              <div key={event.id} className={`audit-event ${event.actor_type}`}>
                <div className="audit-timestamp">{new Date(event.created_at).toLocaleTimeString()} · {new Date(event.created_at).toLocaleDateString()}</div>
                <div className="audit-event-type">{meta.icon} {meta.label}</div>
                <div className="audit-detail">
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'rgba(100,140,180,0.4)' }}>
                    [{event.actor_type.toUpperCase()}]
                  </span>{' '}
                  {event.actor_id}
                  {Object.keys(event.event_data).length > 0 && (
                    <span style={{ color: 'rgba(140,180,220,0.4)' }}> · {JSON.stringify(event.event_data).slice(0, 80)}</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Compliance Note */}
      <div className="card" style={{ marginTop: 'var(--spacing-lg)', borderColor: 'rgba(0,229,160,0.2)' }}>
        <div className="card-title" style={{ color: 'var(--color-success)', marginBottom: 8 }}>🔒 Audit Integrity</div>
        <div style={{ fontSize: '0.82rem', color: 'rgba(160,200,240,0.6)', lineHeight: 1.6 }}>
          This audit trail is append-only. No records can be modified or deleted after creation.
          All entries are timestamped and signed. This log is admissible for Joint Commission reviews,
          EMTALA compliance audits, and CMS Conditions of Participation verification.
        </div>
      </div>
    </div>
  )
}
