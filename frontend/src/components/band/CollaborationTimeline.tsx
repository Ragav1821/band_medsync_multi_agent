/**
 * CollaborationTimeline — Phase 18
 * Shows LIVE inter-agent messages (from agent:message WebSocket events)
 * plus the standard agent:started / agent:completed / plan:ready events.
 *
 * Falls back to DEMO data if no live feed is available.
 */
import { useStore, type WSAgentEvent, type AgentMessage } from '../../store/appStore'

interface TimelineEntry {
  time: string
  from: string
  to: string
  fromIcon: string
  toIcon: string
  fromColor: string
  toColor: string
  label: string
  type: 'dispatch' | 'response' | 'escalation' | 'approval' | 'plan' | 'peer_msg' | 'negotiation_revision' | 'negotiation_replan' | 'negotiation_approved' | 'negotiation_completed'
  messageType?: string
  round?: number
}

const AGENT_META: Record<string, { icon: string; short: string; color: string }> = {
  incident_commander: { icon: '🎯', short: 'Commander', color: '#00a3ff' },
  capacity_agent:     { icon: '🏥', short: 'Capacity',  color: '#00e5a0' },
  staffing_agent:     { icon: '👩‍⚕️', short: 'Staffing', color: '#f59e0b' },
  resource_agent:     { icon: '📦', short: 'Resource',  color: '#a78bfa' },
  compliance_agent:   { icon: '⚖️', short: 'Compliance', color: '#fb923c' },
  system:             { icon: '🚨', short: 'System',     color: '#ff3b5c' },
  human:              { icon: '👤', short: 'Alex Chen',  color: '#00e5a0' },
}

const MSG_TYPE_LABELS: Record<string, string> = {
  capacity_alert:      'CAPACITY ALERT',
  occupancy_warning:   'OCCUPANCY WARN',
  staffing_gap:        'STAFFING GAP',
  staffing_request:    'STAFFING REQ',
  resource_shortage:   'RESOURCE SHORT',
  equipment_constraint:'EQUIP CONSTRAINT',
  approval:            'APPROVED',
  rejection:           'REJECTED',
  policy_warning:      'POLICY WARN',
  assignment:          'ASSIGNMENT',
  escalation:          'ESCALATION',
  clarification_request:'CLARIFICATION',
  // Phase 19A: negotiation message types
  revision_request:    'REVISION REQ',
  replan_request:      'REPLAN REQ',
  replan_response:     'REPLAN RESP',
}

function buildTimeline(
  feedEvents: WSAgentEvent[],
  agentMessages: AgentMessage[],
): TimelineEntry[] {
  const entries: TimelineEntry[] = []
  const seen = new Set<string>()

  // Sort by timestamp
  const sorted = [...feedEvents].sort((a, b) => {
    const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0
    const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0
    return ta - tb
  })

  const fmtTime = (ts?: string) =>
    ts
      ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  for (const event of sorted) {
    const time = fmtTime(event.timestamp)

    // Phase 18 agent:message events
    if (event.event_type === 'agent:message' && event.sender && event.receiver) {
      const key = `msg:${event.sender}:${event.receiver}:${event.message_type}:${event.timestamp}`
      if (!seen.has(key)) {
        seen.add(key)
        const fromMeta = AGENT_META[event.sender] ?? { icon: '🤖', short: event.sender, color: '#888' }
        const toMeta   = AGENT_META[event.receiver] ?? { icon: '🤖', short: event.receiver, color: '#888' }
        entries.push({
          time,
          from: fromMeta.short,
          to: toMeta.short,
          fromIcon: fromMeta.icon,
          toIcon: toMeta.icon,
          fromColor: fromMeta.color,
          toColor: toMeta.color,
          label: event.content ? event.content.slice(0, 80) + (event.content.length > 80 ? '…' : '') : '',
          type: 'peer_msg',
          messageType: event.message_type,
        })
      }
      continue
    }

    if (event.event_type === 'agent:started' && event.agent_name) {
      const key = `started:${event.agent_name}`
      if (!seen.has(key)) {
        seen.add(key)
        const fromMeta = AGENT_META['incident_commander']
        const toMeta   = AGENT_META[event.agent_name] ?? { icon: '🤖', short: event.agent_name, color: '#888' }
        entries.push({
          time,
          from: 'Commander',
          to: toMeta.short,
          fromIcon: fromMeta.icon,
          toIcon: toMeta.icon,
          fromColor: fromMeta.color,
          toColor: toMeta.color,
          label: `Dispatched analysis task`,
          type: 'dispatch',
        })
      }
    }

    if (event.event_type === 'agent:completed' && event.agent_name && event.agent_name !== 'incident_commander') {
      const key = `completed:${event.agent_name}`
      if (!seen.has(key)) {
        seen.add(key)
        const fromMeta = AGENT_META[event.agent_name] ?? { icon: '🤖', short: event.agent_name, color: '#888' }
        const toMeta   = AGENT_META['incident_commander']
        entries.push({
          time,
          from: fromMeta.short,
          to: 'Commander',
          fromIcon: fromMeta.icon,
          toIcon: toMeta.icon,
          fromColor: fromMeta.color,
          toColor: toMeta.color,
          label: event.output_summary
            ? event.output_summary.slice(0, 60) + (event.output_summary.length > 60 ? '…' : '')
            : 'Analysis delivered',
          type: 'response',
        })
      }
    }

    if (event.event_type === 'plan:ready') {
      const key = 'plan:ready'
      if (!seen.has(key)) {
        seen.add(key)
        const fromMeta = AGENT_META['incident_commander']
        entries.push({
          time,
          from: 'Commander',
          to: 'Human Approval',
          fromIcon: fromMeta.icon,
          toIcon: '👤',
          fromColor: fromMeta.color,
          toColor: '#00e5a0',
          label: 'Action plan synthesized — awaiting authorization',
          type: 'plan',
        })
      }
    }

    if (event.event_type === 'alert:escalation') {
      const key = 'escalation'
      if (!seen.has(key)) {
        seen.add(key)
        entries.push({
          time,
          from: 'Commander',
          to: 'CMO / CEO',
          fromIcon: '🎯',
          toIcon: '⬆️',
          fromColor: '#00a3ff',
          toColor: '#ff3b5c',
          label: event.message ?? 'Critical escalation triggered',
          type: 'escalation',
        })
      }
    }

    // Phase 19A: Negotiation lifecycle events
    if (event.event_type === 'negotiation:revision_requested') {
      const key = `neg:revision:${event.timestamp}`
      if (!seen.has(key)) {
        seen.add(key)
        entries.push({
          time,
          from: 'Compliance',
          to: 'Commander',
          fromIcon: '⚖️',
          toIcon: '🎯',
          fromColor: '#fb923c',
          toColor: '#ff3b5c',
          label: (event as any).message ?? 'Compliance requested plan revision',
          type: 'negotiation_revision',
          round: (event as any).round,
        })
      }
    }
    if (event.event_type === 'negotiation:replanning_started') {
      const key = `neg:replan:${event.timestamp}`
      if (!seen.has(key)) {
        seen.add(key)
        entries.push({
          time,
          from: 'Commander',
          to: 'Agents',
          fromIcon: '🎯',
          toIcon: '🔁',
          fromColor: '#00a3ff',
          toColor: '#3b82f6',
          label: (event as any).message ?? 'Replan cycle initiated',
          type: 'negotiation_replan',
          round: (event as any).replan_number,
        })
      }
    }
    if (event.event_type === 'negotiation:reapproved') {
      const key = `neg:reapproved:${event.timestamp}`
      if (!seen.has(key)) {
        seen.add(key)
        entries.push({
          time,
          from: 'Compliance',
          to: 'Commander',
          fromIcon: '⚖️',
          toIcon: '✅',
          fromColor: '#22c55e',
          toColor: '#00a3ff',
          label: (event as any).message ?? 'Revised plan approved',
          type: 'negotiation_approved',
          round: (event as any).round,
        })
      }
    }
    if (event.event_type === 'negotiation:completed') {
      const key = `neg:completed:${event.timestamp}`
      if (!seen.has(key)) {
        seen.add(key)
        const finalStatus = (event as any).final_status
        entries.push({
          time,
          from: 'System',
          to: 'All',
          fromIcon: finalStatus === 'approved' ? '✅' : '⚠️',
          toIcon: '📣',
          fromColor: finalStatus === 'approved' ? '#22c55e' : '#94a3b8',
          toColor: finalStatus === 'approved' ? '#22c55e' : '#94a3b8',
          label: (event as any).message ?? `Negotiation ${finalStatus}`,
          type: 'negotiation_completed',
          round: (event as any).rounds_used,
        })
      }
    }
  }

  return entries
}

// Fallback demo data with Phase 18 peer messages + Phase 19A negotiation events
const DEMO_TIMELINE: TimelineEntry[] = [
  { time: '09:01:02', from: 'Commander', to: 'Capacity',  fromIcon: '🎯', toIcon: '🏥', fromColor: '#00a3ff', toColor: '#00e5a0', label: '[Round 1] Analyze ICU & bed availability', type: 'dispatch' },
  { time: '09:01:44', from: 'Capacity',  to: 'Staffing',  fromIcon: '🏥', toIcon: '👩‍⚕️', fromColor: '#00e5a0', toColor: '#f59e0b', label: 'ICU projected at 104% — 6 additional ICU nurses needed immediately', type: 'peer_msg', messageType: 'capacity_alert' },
  { time: '09:01:44', from: 'Capacity',  to: 'Resource',  fromIcon: '🏥', toIcon: '📦', fromColor: '#00e5a0', toColor: '#a78bfa', label: 'ICU at 104% with 85 incoming — ventilator demand will spike', type: 'peer_msg', messageType: 'occupancy_warning' },
  { time: '09:02:31', from: 'Staffing',  to: 'Commander', fromIcon: '👩‍⚕️', toIcon: '🎯', fromColor: '#f59e0b', toColor: '#00a3ff', label: '[Round 2] 14-nurse gap — 6 on-call activatable', type: 'response' },
  { time: '09:02:31', from: 'Staffing',  to: 'Resource',  fromIcon: '👩‍⚕️', toIcon: '📦', fromColor: '#f59e0b', toColor: '#a78bfa', label: 'Gap of 14 nurses — ensure equipment for 10 ICU positions', type: 'peer_msg', messageType: 'staffing_gap' },
  { time: '09:02:31', from: 'Staffing',  to: 'Compliance', fromIcon: '👩‍⚕️', toIcon: '⚖️', fromColor: '#f59e0b', toColor: '#fb923c', label: 'Ratio at 54% — below threshold, CMO exception documentation required', type: 'peer_msg', messageType: 'staffing_request' },
  { time: '09:03:05', from: 'Resource',  to: 'Commander', fromIcon: '📦', toIcon: '🎯', fromColor: '#a78bfa', toColor: '#00a3ff', label: '[Round 2] 3 ventilator deficit — mutual aid needed', type: 'response' },
  { time: '09:03:05', from: 'Resource',  to: 'Compliance', fromIcon: '📦', toIcon: '⚖️', fromColor: '#a78bfa', toColor: '#fb923c', label: '3 ventilator deficit — State Emergency Code authorization needed', type: 'peer_msg', messageType: 'resource_shortage' },
  // Phase 19A: Negotiation events
  { time: '09:04:12', from: 'Compliance', to: 'Commander', fromIcon: '⚖️', toIcon: '🎯', fromColor: '#fb923c', toColor: '#ff3b5c', label: '🔄 REVISION REQUIRED: 3 unresolved compliance issues', type: 'negotiation_revision', messageType: 'revision_request', round: 1 },
  { time: '09:04:15', from: 'Commander', to: 'Agents',    fromIcon: '🎯', toIcon: '🔁', fromColor: '#00a3ff', toColor: '#3b82f6', label: '🔁 Replan cycle 1/3 — Resource + Staffing revising plans', type: 'negotiation_replan', round: 1 },
  { time: '09:05:30', from: 'Compliance', to: 'Commander', fromIcon: '⚖️', toIcon: '✅', fromColor: '#22c55e', toColor: '#00a3ff', label: '✅ Revised plan APPROVED on round 2 — alternative sourcing accepted', type: 'negotiation_approved', round: 2 },
  { time: '09:05:32', from: 'System',    to: 'All',       fromIcon: '✅', toIcon: '📣', fromColor: '#22c55e', toColor: '#22c55e', label: 'Negotiation complete: APPROVED after 1 replan cycle', type: 'negotiation_completed', round: 2 },
  { time: '09:06:00', from: 'Commander', to: 'Human Approval', fromIcon: '🎯', toIcon: '👤', fromColor: '#00a3ff', toColor: '#00e5a0', label: 'Action plan synthesized — awaiting authorization', type: 'plan' },
]

const TYPE_CONFIG: Record<string, { bar: string; label: string; arrow: string }> = {
  dispatch:               { bar: '#00a3ff', label: 'DISPATCH',     arrow: '→' },
  response:               { bar: '#00e5a0', label: 'RESPONSE',     arrow: '←' },
  escalation:             { bar: '#ff3b5c', label: 'ESCALATION',   arrow: '⬆' },
  approval:               { bar: '#00e5a0', label: 'APPROVAL',     arrow: '✓' },
  plan:                   { bar: '#a78bfa', label: 'PLAN READY',   arrow: '→' },
  peer_msg:               { bar: '#f59e0b', label: 'PEER MSG',     arrow: '⇄' },
  // Phase 19A: negotiation event types
  negotiation_revision:   { bar: '#ff3b5c', label: '🔄 REVISION',  arrow: '→' },
  negotiation_replan:     { bar: '#3b82f6', label: '🔁 REPLAN',    arrow: '⇄' },
  negotiation_approved:   { bar: '#22c55e', label: '✅ APPROVED',  arrow: '✓' },
  negotiation_completed:  { bar: '#94a3b8', label: '🏁 COMPLETE',  arrow: '✓' },
}

export function CollaborationTimeline() {
  const { selectedIncidentId, feedEvents, agentMessages } = useStore()

  const currentFeed     = feedEvents.filter(e => !selectedIncidentId || e.incident_id === selectedIncidentId)
  const currentMsgs     = selectedIncidentId ? (agentMessages[selectedIncidentId] ?? []) : []
  const liveTimeline    = buildTimeline(currentFeed, currentMsgs)
  const timeline        = liveTimeline.length > 0 ? liveTimeline : DEMO_TIMELINE
  const peerMsgCount    = timeline.filter(e => e.type === 'peer_msg').length

  return (
    <div className="card" style={{ borderColor: 'rgba(0,163,255,0.2)' }}>
      <div className="card-header" style={{ marginBottom: 16 }}>
        <div className="card-title">
          🤝 Agent Collaboration Timeline
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {liveTimeline.length > 0 && (
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#00e5a0', boxShadow: '0 0 8px #00e5a0', animation: 'operational-pulse 2s infinite' }} />
          )}
          <span className={`badge ${liveTimeline.length > 0 ? 'badge-success' : 'badge-info'}`}>
            {liveTimeline.length > 0 ? 'LIVE' : 'DEMO'}
          </span>
          <span className="badge badge-accent">{timeline.length} events</span>
          {peerMsgCount > 0 && (
            <span className="badge" style={{ background: 'rgba(245,158,11,0.2)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)' }}>
              ⇄ {peerMsgCount} peer msgs
            </span>
          )}
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        {Object.entries(TYPE_CONFIG).map(([type, cfg]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: cfg.bar, opacity: 0.8 }} />
            <span style={{ fontSize: '0.62rem', color: 'rgba(140,180,220,0.5)', fontFamily: 'var(--font-mono)' }}>{cfg.label}</span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 380, overflowY: 'auto' }}>
        {timeline.map((entry, i) => {
          const cfg = TYPE_CONFIG[entry.type]
          const isPeerMsg = entry.type === 'peer_msg'
          const msgTypeLabel = entry.messageType ? (MSG_TYPE_LABELS[entry.messageType] ?? entry.messageType.toUpperCase()) : null
          return (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '70px 1fr auto',
              gap: 10, alignItems: 'center',
              padding: '7px 10px',
              background: isPeerMsg ? 'rgba(245,158,11,0.04)' : 'rgba(255,255,255,0.02)',
              borderRadius: 8,
              border: isPeerMsg ? '1px solid rgba(245,158,11,0.12)' : '1px solid rgba(255,255,255,0.04)',
              borderLeft: `3px solid ${cfg.bar}${isPeerMsg ? 'cc' : '60'}`,
            }}>
              {/* Time */}
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.62rem', color: 'rgba(140,180,220,0.35)' }}>
                {entry.time}
              </div>

              {/* Message flow */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 700,
                    color: entry.fromColor,
                    padding: '1px 6px', borderRadius: 4,
                    background: `${entry.fromColor}15`,
                    border: `1px solid ${entry.fromColor}30`,
                    whiteSpace: 'nowrap',
                  }}>
                    {entry.fromIcon} {entry.from}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: cfg.bar, fontWeight: 700 }}>{cfg.arrow}</span>
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 700,
                    color: entry.toColor,
                    padding: '1px 6px', borderRadius: 4,
                    background: `${entry.toColor}15`,
                    border: `1px solid ${entry.toColor}30`,
                    whiteSpace: 'nowrap',
                  }}>
                    {entry.toIcon} {entry.to}
                  </span>
                  {msgTypeLabel && (
                    <span style={{
                      fontSize: '0.55rem', fontFamily: 'var(--font-mono)', fontWeight: 700,
                      color: '#f59e0b', padding: '1px 5px', borderRadius: 3,
                      background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.2)',
                      whiteSpace: 'nowrap',
                    }}>
                      {msgTypeLabel}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'rgba(160,200,240,0.65)', lineHeight: 1.4 }}>
                  {entry.label}
                </div>
              </div>

              {/* Type badge */}
              <div style={{
                fontSize: '0.58rem', fontFamily: 'var(--font-mono)', fontWeight: 700,
                color: cfg.bar, padding: '2px 6px', borderRadius: 4,
                background: `${cfg.bar}15`, border: `1px solid ${cfg.bar}30`,
                whiteSpace: 'nowrap',
              }}>
                {cfg.label}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
