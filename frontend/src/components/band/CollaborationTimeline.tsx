import { useStore, type WSAgentEvent } from '../../store/appStore'

interface TimelineEntry {
  time: string
  from: string
  to: string
  fromIcon: string
  toIcon: string
  fromColor: string
  toColor: string
  label: string
  type: 'dispatch' | 'response' | 'escalation' | 'approval' | 'plan'
}

const AGENT_META: Record<string, { icon: string; short: string; color: string }> = {
  incident_commander: { icon: '🎯', short: 'Commander', color: '#00a3ff' },
  capacity_agent: { icon: '🏥', short: 'Capacity', color: '#00e5a0' },
  staffing_agent: { icon: '👩‍⚕️', short: 'Staffing', color: '#f59e0b' },
  resource_agent: { icon: '📦', short: 'Resource', color: '#a78bfa' },
  compliance_agent: { icon: '⚖️', short: 'Compliance', color: '#fb923c' },
  system: { icon: '🚨', short: 'System', color: '#ff3b5c' },
  human: { icon: '👤', short: 'Alex Chen', color: '#00e5a0' },
}

function buildTimeline(feedEvents: WSAgentEvent[]): TimelineEntry[] {
  const entries: TimelineEntry[] = []
  const seen = new Set<string>()

  // Sort by timestamp
  const sorted = [...feedEvents].sort((a, b) => {
    const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0
    const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0
    return ta - tb
  })

  for (const event of sorted) {
    const time = event.timestamp
      ? new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

    if (event.event_type === 'agent:started' && event.agent_name) {
      const key = `started:${event.agent_name}`
      if (!seen.has(key)) {
        seen.add(key)
        const fromMeta = AGENT_META['incident_commander']
        const toMeta = AGENT_META[event.agent_name] ?? { icon: '🤖', short: event.agent_name, color: '#888' }
        entries.push({
          time, from: 'Commander', to: toMeta.short,
          fromIcon: fromMeta.icon, toIcon: toMeta.icon,
          fromColor: fromMeta.color, toColor: toMeta.color,
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
        const toMeta = AGENT_META['incident_commander']
        entries.push({
          time, from: fromMeta.short, to: 'Commander',
          fromIcon: fromMeta.icon, toIcon: toMeta.icon,
          fromColor: fromMeta.color, toColor: toMeta.color,
          label: event.output_summary ? event.output_summary.slice(0, 60) + (event.output_summary.length > 60 ? '…' : '') : 'Analysis delivered',
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
          time, from: 'Commander', to: 'Human Approval',
          fromIcon: fromMeta.icon, toIcon: '👤',
          fromColor: fromMeta.color, toColor: '#00e5a0',
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
          time, from: 'Commander', to: 'CMO / CEO',
          fromIcon: '🎯', toIcon: '⬆️',
          fromColor: '#00a3ff', toColor: '#ff3b5c',
          label: event.message ?? 'Critical escalation triggered',
          type: 'escalation',
        })
      }
    }
  }

  return entries
}

// Fallback demo data when no live feed
const DEMO_TIMELINE: TimelineEntry[] = [
  { time: '09:01:02', from: 'Commander', to: 'Capacity', fromIcon: '🎯', toIcon: '🏥', fromColor: '#00a3ff', toColor: '#00e5a0', label: 'Dispatch: Analyze ICU & bed availability', type: 'dispatch' },
  { time: '09:01:02', from: 'Commander', to: 'Staffing', fromIcon: '🎯', toIcon: '👩‍⚕️', fromColor: '#00a3ff', toColor: '#f59e0b', label: 'Dispatch: Compute nurse gap for 35 patients', type: 'dispatch' },
  { time: '09:01:02', from: 'Commander', to: 'Resource', fromIcon: '🎯', toIcon: '📦', fromColor: '#00a3ff', toColor: '#a78bfa', label: 'Dispatch: Inventory ventilators & blood supply', type: 'dispatch' },
  { time: '09:02:14', from: 'Capacity', to: 'Commander', fromIcon: '🏥', toIcon: '🎯', fromColor: '#00e5a0', toColor: '#00a3ff', label: 'Report: ICU 92% — 8 patients transferable (conf. 94%)', type: 'response' },
  { time: '09:02:31', from: 'Staffing', to: 'Commander', fromIcon: '👩‍⚕️', toIcon: '🎯', fromColor: '#f59e0b', toColor: '#00a3ff', label: 'Report: 14-nurse gap — 6 on-call activatable (conf. 88%)', type: 'response' },
  { time: '09:03:05', from: 'Resource', to: 'Commander', fromIcon: '📦', toIcon: '🎯', fromColor: '#a78bfa', toColor: '#00a3ff', label: 'Report: 2 ventilators reallocatable, mutual aid needed (conf. 85%)', type: 'response' },
  { time: '09:03:06', from: 'Commander', to: 'Compliance', fromIcon: '🎯', toIcon: '⚖️', fromColor: '#00a3ff', toColor: '#fb923c', label: 'Dispatch: Validate EMTALA compliance for all actions', type: 'dispatch' },
  { time: '09:04:12', from: 'Compliance', to: 'Commander', fromIcon: '⚖️', toIcon: '🎯', fromColor: '#fb923c', toColor: '#00a3ff', label: 'Report: CONDITIONALLY_COMPLIANT — 5 docs required', type: 'response' },
  { time: '09:05:00', from: 'Commander', to: 'Human Approval', fromIcon: '🎯', toIcon: '👤', fromColor: '#00a3ff', toColor: '#00e5a0', label: 'Action plan synthesized — awaiting authorization', type: 'plan' },
]

const TYPE_CONFIG = {
  dispatch: { bar: '#00a3ff', label: 'DISPATCH', arrow: '→' },
  response: { bar: '#00e5a0', label: 'RESPONSE', arrow: '←' },
  escalation: { bar: '#ff3b5c', label: 'ESCALATION', arrow: '⬆' },
  approval: { bar: '#00e5a0', label: 'APPROVAL', arrow: '✓' },
  plan: { bar: '#a78bfa', label: 'PLAN READY', arrow: '→' },
}

export function CollaborationTimeline() {
  const { selectedIncidentId, feedEvents } = useStore()

  const currentFeed = feedEvents.filter(e => !selectedIncidentId || e.incident_id === selectedIncidentId)
  const liveTimeline = buildTimeline(currentFeed)
  const timeline = liveTimeline.length > 0 ? liveTimeline : DEMO_TIMELINE

  return (
    <div className="card" style={{ borderColor: 'rgba(0,163,255,0.2)' }}>
      <div className="card-header" style={{ marginBottom: 16 }}>
        <div className="card-title">
          💬 Band Collaboration Timeline
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {liveTimeline.length > 0 && (
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#00e5a0', boxShadow: '0 0 8px #00e5a0', animation: 'operational-pulse 2s infinite' }} />
          )}
          <span className={`badge ${liveTimeline.length > 0 ? 'badge-success' : 'badge-info'}`}>
            {liveTimeline.length > 0 ? 'LIVE' : 'DEMO'}
          </span>
          <span className="badge badge-accent">{timeline.length} messages</span>
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 340, overflowY: 'auto' }}>
        {timeline.map((entry, i) => {
          const cfg = TYPE_CONFIG[entry.type]
          const isDispatch = entry.type === 'dispatch'
          return (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '70px 1fr auto',
              gap: 10, alignItems: 'center',
              padding: '7px 10px',
              background: 'rgba(255,255,255,0.02)',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.04)',
              borderLeft: `3px solid ${cfg.bar}60`,
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
                  <span style={{
                    fontSize: '0.7rem', color: cfg.bar,
                    transform: isDispatch ? 'none' : 'none',
                  }}>{cfg.arrow}</span>
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
