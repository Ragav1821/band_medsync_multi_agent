import { useEffect, useState } from 'react'
import { useStore } from '../store/appStore'
import { actionPlanApi, type ActionPlan, type ActionItem, type ExecutiveSummary } from '../api/client'
import { LoginModal } from '../components/shared/LoginModal'

const DEMO_PLAN: ActionPlan = {
  id: 'demo-plan-001',
  incident_id: 'demo',
  status: 'pending',
  severity_level: 3,
  severity_label: 'LEVEL 3 — CRITICAL',
  priority_1_actions: [
    { id: 'a1', description: 'Activate Hospital Surge Protocol Level 3A immediately', responsible_party: 'Hospital Operations Manager', timeline: 'Immediate (0–2 min)', status: 'pending', is_compliant: true },
    { id: 'a2', description: 'Begin transfer of 8 stable ICU patients to Step-Down Unit', responsible_party: 'ICU Administrator', timeline: 'Immediate (0–5 min)', status: 'pending', is_compliant: true },
    { id: 'a3', description: 'Activate mutual aid: contact City General Hospital for 7 ventilators', responsible_party: 'Resource Manager', timeline: 'Immediate (0–5 min)', status: 'pending', is_compliant: true },
  ],
  priority_2_actions: [
    { id: 'b1', description: 'Authorize and activate 6 on-call nurses (30-min ETA)', responsible_party: 'Nursing Supervisor', timeline: '15 minutes', status: 'pending', is_compliant: true },
    { id: 'b2', description: 'Request 8 agency nurses from registered staffing pool', responsible_party: 'Nursing Supervisor', timeline: '15 minutes', status: 'pending', is_compliant: true },
    { id: 'b3', description: 'Reallocate 2 ventilators from elective surgery floor to emergency use', responsible_party: 'Resource Manager', timeline: '15 minutes', status: 'pending', is_compliant: true },
    { id: 'b4', description: 'Contact regional blood center for emergency supply + initiate blood drive', responsible_party: 'Lab / Blood Bank Manager', timeline: '30 minutes', status: 'pending', is_compliant: true },
  ],
  priority_3_actions: [
    { id: 'c1', description: 'Complete: EMTALA Intake Log — document each patient arrival time and initial assessment', responsible_party: 'Compliance / Operations', timeline: '1 hour', status: 'pending', is_compliant: true },
    { id: 'c2', description: 'Complete: Medical Necessity Exception Form — document staffing shortage mitigation', responsible_party: 'Compliance / Operations', timeline: '1 hour', status: 'pending', is_compliant: true },
    { id: 'c3', description: 'Complete: Incident Command Activation Form — log surge protocol start time', responsible_party: 'Compliance / Operations', timeline: '1 hour', status: 'pending', is_compliant: true },
    { id: 'c4', description: 'Complete: Bed Status Report — update state health department within 1 hour', responsible_party: 'Compliance / Operations', timeline: '1 hour', status: 'pending', is_compliant: true },
    { id: 'c5', description: 'Complete: Mutual Aid Agreement Activation Log + Equipment Chain of Custody Form', responsible_party: 'Compliance / Operations', timeline: '1 hour', status: 'pending', is_compliant: true },
  ],
  escalation_items: [
    'NOTIFY CMO: Level 3 Critical event — staffing authorization required',
    'NOTIFY CEO/Hospital Leadership: Mass casualty event active',
    'NOTIFY State Health Department: Surge protocol activated (within 1 hour)',
    'EXECUTIVE DECISION REQUIRED: 4 nurses unresolvable without CMO authorization',
  ],
  compliance_status: 'CONDITIONALLY_COMPLIANT',
  overall_summary: 'Mass casualty event classified LEVEL 3 CRITICAL. All 4 specialist agents coordinated. Final Action Plan: 3 immediate actions, 4 follow-ups, 4 escalations.',
  required_documentation: ['EMTALA Intake Log', 'Transfer Summary Form', 'Incident Command Activation Form'],
  agent_outputs: {},
  created_at: new Date().toISOString(),
}

export function ActionPlanPage({ onNavigate }: { onNavigate: (page: string, id?: string) => void }) {
  const { selectedIncidentId, actionPlans, setActionPlan, incidents, addToast, currentUser, logout } = useStore()
  const [approving, setApproving] = useState(false)
  const [expandedSection, setExpandedSection] = useState<string | null>(null)
  const [showLoginModal, setShowLoginModal] = useState(false)

  const plan = selectedIncidentId ? actionPlans[selectedIncidentId] : null
  const displayPlan = plan || DEMO_PLAN
  const incident = incidents.find(i => i.id === selectedIncidentId)

  useEffect(() => {
    if (!selectedIncidentId) return
    const fetchPlan = async () => {
      try {
        const res = await actionPlanApi.get(selectedIncidentId)
        setActionPlan(selectedIncidentId, res.data)
      } catch {
        // use demo
      }
    }
    fetchPlan()
    const interval = setInterval(fetchPlan, 5000)
    return () => clearInterval(interval)
  }, [selectedIncidentId, setActionPlan])

  const handleApproveClick = () => {
    // P0-2: Gate approval behind authentication
    if (!currentUser) {
      setShowLoginModal(true)
      return
    }
    doApprove()
  }

  const doApprove = async () => {
    if (!displayPlan.id) return
    setApproving(true)
    try {
      // P0-3: identity comes from JWT token — no query param passed
      await actionPlanApi.approve(displayPlan.id)
      addToast({
        type: 'success',
        title: '✅ Plan Approved',
        message: `Approved by ${currentUser?.display_name}. Notifications dispatched to all departments.`,
      })
      if (selectedIncidentId) {
        const res = await actionPlanApi.get(selectedIncidentId)
        setActionPlan(selectedIncidentId, res.data)
      }
    } catch {
      addToast({ type: 'success', title: '✅ Plan Approved (Demo)', message: 'Action plan approved. Notifications would be dispatched in production.' })
    } finally {
      setApproving(false)
    }
  }

  const complianceBadge = {
    FULLY_COMPLIANT: { class: 'badge-success', label: '✅ Fully Compliant' },
    CONDITIONALLY_COMPLIANT: { class: 'badge-warning', label: '⚠️ Conditionally Compliant' },
    REQUIRES_REVIEW: { class: 'badge-critical', label: '🚨 Requires Review' },
    UNKNOWN: { class: 'badge-info', label: 'Pending Validation' },
  }[displayPlan.compliance_status] ?? { class: 'badge-info', label: displayPlan.compliance_status }

  return (
    <div>
      {/* P0-2: Login modal — shown when user tries to approve without auth */}
      {showLoginModal && (
        <LoginModal
          onClose={() => setShowLoginModal(false)}
          onSuccess={() => doApprove()}
        />
      )}

      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 className="page-title">📋 Final Action Plan</h1>
            <p className="page-subtitle">AI-generated coordinated response — awaiting authorization</p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {/* P0-3: Show authenticated user identity */}
            {currentUser && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 8, background: 'rgba(0,229,160,0.1)', border: '1px solid rgba(0,229,160,0.25)' }}>
                <span style={{ fontSize: '0.7rem', color: '#00e5a0' }}>🔐 {currentUser.display_name}</span>
                <button onClick={logout} style={{ background: 'none', border: 'none', color: 'rgba(160,200,240,0.4)', cursor: 'pointer', fontSize: '0.65rem', padding: '0 2px' }}>✕</button>
              </div>
            )}
            {displayPlan.status !== 'approved' && (
              <button className="btn btn-success" onClick={handleApproveClick} disabled={approving}>
                {approving ? '⏳ Approving...' : '✅ Approve & Execute'}
              </button>
            )}
            {displayPlan.status === 'approved' && (
              <span className="badge badge-success" style={{ padding: '8px 16px', fontSize: '0.8rem' }}>✅ APPROVED & EXECUTING</span>
            )}
          </div>
        </div>
      </div>

      {/* Summary Header */}
      <div className="card" style={{ marginBottom: 'var(--spacing-lg)', borderColor: 'rgba(255,59,92,0.3)', background: 'rgba(255,59,92,0.04)' }}>
        <div style={{ display: 'flex', gap: 'var(--spacing-lg)', alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <span className="badge badge-critical" style={{ marginBottom: 6, display: 'inline-block' }}>{displayPlan.severity_label}</span>
            <div style={{ color: 'white', fontSize: '0.9rem', lineHeight: 1.6 }}>{displayPlan.overall_summary}</div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
            <span className={`badge ${complianceBadge.class}`}>{complianceBadge.label}</span>
            <div style={{ fontSize: '0.7rem', color: 'rgba(140,180,220,0.4)', fontFamily: 'var(--font-mono)' }}>
              Generated: {new Date(displayPlan.created_at).toLocaleTimeString()}
            </div>
          </div>
        </div>

        {/* Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--spacing-sm)', marginTop: 'var(--spacing-md)', paddingTop: 'var(--spacing-md)', borderTop: '1px solid var(--color-border)' }}>
          <StatBubble label="Immediate Actions" value={displayPlan.priority_1_actions?.length ?? 0} color="var(--color-critical)" />
          <StatBubble label="Follow-up Actions" value={displayPlan.priority_2_actions?.length ?? 0} color="var(--color-warning)" />
          <StatBubble label="Documentation" value={displayPlan.priority_3_actions?.length ?? 0} color="var(--color-success)" />
          <StatBubble label="Escalations" value={displayPlan.escalation_items?.length ?? 0} color="var(--color-info)" />
        </div>
      </div>

      {/* AI Executive Summary (Gemini or rule-based fallback) */}
      {displayPlan.executive_summary && (
        <div className="card" style={{ marginBottom: 'var(--spacing-lg)', borderColor: 'rgba(0,163,255,0.25)', background: 'rgba(0,163,255,0.04)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-md)' }}>
            <div className="card-title" style={{ color: 'var(--color-accent)', margin: 0 }}>
              🧠 Executive Summary
            </div>
            <span
              className={`badge ${displayPlan.executive_summary.ai_generated ? 'badge-success' : 'badge-info'}`}
              style={{ fontSize: '0.68rem' }}
            >
              {displayPlan.executive_summary.ai_generated ? '⚡ Gemini AI' : '📊 Rule-based'}
            </span>
          </div>

          {/* Narrative */}
          <p style={{ color: 'rgba(180,220,255,0.85)', fontSize: '0.88rem', lineHeight: 1.7, margin: '0 0 var(--spacing-md)' }}>
            {displayPlan.executive_summary.executive_summary}
          </p>

          {/* Critical Risks */}
          {displayPlan.executive_summary.critical_risks?.length > 0 && (
            <div style={{ marginBottom: 'var(--spacing-md)' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-critical)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                🔴 Critical Risks
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {displayPlan.executive_summary.critical_risks.map((risk, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: '0.82rem', color: 'rgba(255,180,180,0.85)' }}>
                    <span style={{ color: 'var(--color-critical)', flexShrink: 0, marginTop: 2 }}>▸</span>
                    <span>{risk}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Action Plan */}
          {displayPlan.executive_summary.action_plan?.length > 0 && (
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-warning)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                ⚡ Top Actions (AI Synthesis)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {displayPlan.executive_summary.action_plan.map((item, i) => (
                  <div key={i} style={{ display: 'grid', gridTemplateColumns: '24px 1fr 120px 80px', gap: 8, alignItems: 'center', fontSize: '0.78rem', padding: '5px 0', borderBottom: '1px solid var(--color-border)' }}>
                    <span style={{ fontWeight: 700, color: 'var(--color-accent)', textAlign: 'center' }}>{item.priority}</span>
                    <span style={{ color: 'rgba(200,230,255,0.8)' }}>{item.action}</span>
                    <span style={{ color: 'rgba(140,180,220,0.5)', fontSize: '0.72rem', textAlign: 'right' }}>{item.owner}</span>
                    <span style={{ color: 'var(--color-success)', fontSize: '0.72rem', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{item.eta}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action Plan Sections */}
      <div className="action-plan">
        <PrioritySection
          title="🔴 Priority 1 — Immediate Actions"
          subtitle="Execute within 0–5 minutes"
          headerClass="p1"
          items={displayPlan.priority_1_actions ?? []}
          expanded={expandedSection !== 'p1'}
          onToggle={() => setExpandedSection(prev => prev === 'p1' ? null : 'p1')}
        />
        <PrioritySection
          title="🟡 Priority 2 — Short-term Actions"
          subtitle="Execute within 15–30 minutes"
          headerClass="p2"
          items={displayPlan.priority_2_actions ?? []}
          expanded={expandedSection !== 'p2'}
          onToggle={() => setExpandedSection(prev => prev === 'p2' ? null : 'p2')}
        />
        <PrioritySection
          title="🟢 Priority 3 — Documentation & Compliance"
          subtitle="Complete within 1 hour"
          headerClass="p3"
          items={displayPlan.priority_3_actions ?? []}
          expanded={expandedSection !== 'p3'}
          onToggle={() => setExpandedSection(prev => prev === 'p3' ? null : 'p3')}
        />

        {/* Escalation Items */}
        {displayPlan.escalation_items && displayPlan.escalation_items.length > 0 && (
          <div className="priority-group">
            <div className="priority-header escalation">
              ⬆️ Escalation Notifications · {displayPlan.escalation_items.length} items requiring executive action
            </div>
            {displayPlan.escalation_items.map((item, i) => (
              <div key={i} className="action-item">
                <div className="action-number" style={{ color: 'var(--color-info)', background: 'rgba(167,139,250,0.1)' }}>{i + 1}</div>
                <div className="action-content">
                  <div className="action-description">{item}</div>
                </div>
                <span className="badge badge-critical" style={{ flexShrink: 0 }}>ACTION REQUIRED</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Required Documentation */}
      {displayPlan.required_documentation && displayPlan.required_documentation.length > 0 && (
        <div className="card" style={{ marginTop: 'var(--spacing-lg)' }}>
          <div className="card-title" style={{ marginBottom: 'var(--spacing-md)' }}>📄 Required Documentation Checklist</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {displayPlan.required_documentation.map((doc, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--color-border)', fontSize: '0.82rem' }}>
                <input type="checkbox" style={{ accentColor: 'var(--color-accent)' }} />
                <span style={{ color: 'rgba(180,220,255,0.8)' }}>{doc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatBubble({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '1.8rem', fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.5)', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function PrioritySection({ title, subtitle, headerClass, items, expanded, onToggle }: {
  title: string; subtitle: string; headerClass: string;
  items: ActionItem[]; expanded: boolean; onToggle: () => void
}) {
  return (
    <div className="priority-group">
      <div className={`priority-header ${headerClass}`} onClick={onToggle} style={{ cursor: 'pointer', userSelect: 'none' }}>
        <span style={{ flex: 1 }}>{title}</span>
        <span style={{ fontSize: '0.72rem', opacity: 0.6, marginRight: 8 }}>{subtitle}</span>
        <span style={{ fontSize: '0.8rem' }}>{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && items.map((item, i) => (
        <div key={item.id} className="action-item">
          <div className="action-number">{i + 1}</div>
          <div className="action-content">
            <div className="action-description">{item.description}</div>
            <div className="action-meta">
              <span className="action-party">👤 {item.responsible_party}</span>
              <span className={`action-timeline ${item.timeline.toLowerCase().includes('immediate') ? 'immediate' : item.timeline.toLowerCase().includes('1 hour') ? 'later' : 'short'}`}>
                ⏱ {item.timeline}
              </span>
              {item.is_compliant && <span style={{ fontSize: '0.7rem', color: 'var(--color-success)' }}>✅ Compliant</span>}
            </div>
          </div>
          <div style={{ flexShrink: 0 }}>
            <input type="checkbox" style={{ accentColor: 'var(--color-success)', width: 16, height: 16 }} />
          </div>
        </div>
      ))}
    </div>
  )
}
