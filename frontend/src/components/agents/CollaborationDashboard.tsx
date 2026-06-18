/**
 * CollaborationDashboard — Phase 18 (Task 9)
 * Judge-facing panel showing:
 *   - Active Agents
 *   - Messages Exchanged
 *   - Coordination Events
 *   - Communication Graph (SVG arrows between agent nodes)
 *   - Agent Relationships
 */
import { useStore, type AgentMessage, type CoordinationRound } from '../../store/appStore'

const AGENT_NODES = [
  { id: 'incident_commander', label: 'Commander', icon: '🎯', color: '#00a3ff', x: 200, y: 30 },
  { id: 'capacity_agent',     label: 'Capacity',  icon: '🏥', color: '#00e5a0', x: 50,  y: 150 },
  { id: 'staffing_agent',     label: 'Staffing',  icon: '👩‍⚕️', color: '#f59e0b', x: 130, y: 270 },
  { id: 'resource_agent',     label: 'Resource',  icon: '📦', color: '#a78bfa', x: 270, y: 270 },
  { id: 'compliance_agent',   label: 'Compliance', icon: '⚖️', color: '#fb923c', x: 350, y: 150 },
]

const MSG_TYPE_COLORS: Record<string, string> = {
  capacity_alert:       '#00e5a0',
  occupancy_warning:    '#00e5a0',
  staffing_gap:         '#f59e0b',
  staffing_request:     '#f59e0b',
  resource_shortage:    '#a78bfa',
  equipment_constraint: '#a78bfa',
  approval:             '#22c55e',
  policy_warning:       '#fb923c',
  rejection:            '#ff3b5c',
  assignment:           '#00a3ff',
  escalation:           '#ff3b5c',
  // Phase 19A: negotiation message types
  revision_request:     '#ff3b5c',
  replan_request:       '#00a3ff',
  replan_response:      '#a78bfa',
}

function getNode(id: string) {
  return AGENT_NODES.find(n => n.id === id)
}

function CommunicationGraph({ messages }: { messages: AgentMessage[] }) {
  // Build edge list from messages (deduplicate by sender+receiver pair)
  const edgeMap = new Map<string, { from: string; to: string; count: number; types: Set<string> }>()
  for (const msg of messages) {
    const key = `${msg.sender}→${msg.receiver}`
    if (!edgeMap.has(key)) {
      edgeMap.set(key, { from: msg.sender, to: msg.receiver, count: 0, types: new Set() })
    }
    const edge = edgeMap.get(key)!
    edge.count++
    edge.types.add(msg.message_type)
  }

  const edges = [...edgeMap.values()]
  const SVG_W = 420
  const SVG_H = 320
  const NODE_R = 26

  return (
    <svg width={SVG_W} height={SVG_H} style={{ overflow: 'visible' }}>
      <defs>
        <marker id="arrow-head" markerWidth="8" markerHeight="8" refX="5" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="rgba(255,255,255,0.3)" />
        </marker>
      </defs>

      {/* Edges */}
      {edges.map(({ from, to, count, types }, i) => {
        const fromNode = getNode(from)
        const toNode   = getNode(to)
        if (!fromNode || !toNode) return null

        const primaryType = [...types][0]
        const edgeColor = MSG_TYPE_COLORS[primaryType] ?? '#666'

        // Offset slightly so bidirectional edges don't overlap
        const dx = toNode.x - fromNode.x
        const dy = toNode.y - fromNode.y
        const len = Math.sqrt(dx * dx + dy * dy)
        const nx  = -dy / len
        const ny  =  dx / len
        const offset = edges.find(e2 => e2.from === to && e2.to === from) ? 12 : 0

        const x1 = fromNode.x + nx * offset
        const y1 = fromNode.y + ny * offset
        const x2 = toNode.x   + nx * offset
        const y2 = toNode.y   + ny * offset

        // Shorten line to not overlap node circles
        const shorten = NODE_R + 4
        const fullLen = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        const ux = (x2 - x1) / fullLen
        const uy = (y2 - y1) / fullLen

        const sx = x1 + ux * shorten
        const sy = y1 + uy * shorten
        const ex = x2 - ux * shorten
        const ey = y2 - uy * shorten

        const mx = (sx + ex) / 2
        const my = (sy + ey) / 2

        return (
          <g key={i}>
            <line
              x1={sx} y1={sy} x2={ex} y2={ey}
              stroke={edgeColor}
              strokeWidth={Math.min(3, 1 + count * 0.5)}
              strokeOpacity={0.6}
              markerEnd="url(#arrow-head)"
            />
            {/* Message count badge */}
            <circle cx={mx} cy={my} r={8} fill={`${edgeColor}22`} stroke={edgeColor} strokeOpacity={0.4} strokeWidth={1} />
            <text x={mx} y={my + 4} textAnchor="middle" fontSize="8" fill={edgeColor} fontWeight="700">{count}</text>
          </g>
        )
      })}

      {/* Nodes */}
      {AGENT_NODES.map(node => {
        const nodeMessages = messages.filter(m => m.sender === node.id || m.receiver === node.id)
        const isActive = nodeMessages.length > 0
        return (
          <g key={node.id}>
            {/* Glow ring for active nodes */}
            {isActive && (
              <circle cx={node.x} cy={node.y} r={NODE_R + 6} fill="none"
                stroke={node.color} strokeWidth={1.5} strokeOpacity={0.25} />
            )}
            <circle cx={node.x} cy={node.y} r={NODE_R}
              fill={`${node.color}18`}
              stroke={node.color}
              strokeWidth={isActive ? 2 : 1}
              strokeOpacity={isActive ? 0.8 : 0.3}
            />
            <text x={node.x} y={node.y + 5} textAnchor="middle" fontSize="14">{node.icon}</text>
            <text x={node.x} y={node.y + NODE_R + 14} textAnchor="middle"
              fontSize="9" fill={isActive ? node.color : 'rgba(160,200,240,0.4)'} fontWeight="700">
              {node.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color: string }) {
  return (
    <div style={{
      padding: '12px 16px', borderRadius: 10,
      background: `${color}0d`,
      border: `1px solid ${color}25`,
    }}>
      <div style={{ fontSize: '1.4rem', fontWeight: 800, color }}>{value}</div>
      <div style={{ fontSize: '0.7rem', color: 'rgba(160,200,240,0.6)', marginTop: 2 }}>{label}</div>
      {sub && <div style={{ fontSize: '0.65rem', color: `${color}99`, marginTop: 3 }}>{sub}</div>}
    </div>
  )
}

// ── Phase 19A: Negotiation Status Panel ──────────────────────────────────────

const STATUS_BADGES: Record<string, { label: string; color: string; pulse?: boolean }> = {
  initial:         { label: 'IDLE',             color: '#64748b' },
  replanning:      { label: 'REPLANNING',       color: '#3b82f6', pulse: true },
  approved:        { label: 'APPROVED',         color: '#22c55e' },
  rejected:        { label: 'REJECTED',         color: '#ff3b5c' },
  force_finalized: { label: 'FORCE FINALIZED',  color: '#94a3b8' },
}

function NegotiationStatusPanel({ coordRound }: { coordRound: CoordinationRound | null }) {
  const status = coordRound?.status ?? 'initial'
  const badge = STATUS_BADGES[status] ?? STATUS_BADGES.initial
  const log = coordRound?.negotiation_log ?? []

  const EVENT_ICONS: Record<string, { icon: string; color: string }> = {
    ROUND_1_COMPLETE:    { icon: '1️⃣', color: '#00e5a0' },
    ROUND_2_COMPLETE:    { icon: '2️⃣', color: '#f59e0b' },
    ROUND_3_COMPLETE:    { icon: '3️⃣', color: '#a78bfa' },
    NEGOTIATION_STARTED: { icon: '🔁', color: '#3b82f6' },
    REVISION_REQUESTED:  { icon: '🔄', color: '#ff3b5c' },
    REPLAN_REQUEST_ISSUED:{ icon: '📤', color: '#00a3ff' },
    AGENTS_REVISED:      { icon: '📝', color: '#a78bfa' },
    COMPLIANCE_RECHECKED:{ icon: '⚖️', color: '#fb923c' },
    APPROVED:            { icon: '✅', color: '#22c55e' },
    FORCE_FINALIZED:     { icon: '⚠️', color: '#94a3b8' },
    POLICY_WARNING:      { icon: '⚠️', color: '#fb923c' },
  }

  return (
    <div style={{
      background: 'rgba(0,0,0,0.15)', borderRadius: 10,
      border: `1px solid ${badge.color}30`,
      padding: '14px 16px',
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: 1, color: 'rgba(160,200,240,0.5)' }}>
          NEGOTIATION STATUS
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Round badge */}
          <span style={{
            fontSize: '0.62rem', fontFamily: 'var(--font-mono)', fontWeight: 700,
            color: '#00a3ff', padding: '2px 8px', borderRadius: 4,
            background: 'rgba(0,163,255,0.12)', border: '1px solid rgba(0,163,255,0.25)',
          }}>
            ROUND {coordRound?.current_round ?? 1}/{coordRound?.max_rounds ?? 3}
          </span>
          {/* Revision count */}
          {(coordRound?.revision_count ?? 0) > 0 && (
            <span style={{
              fontSize: '0.62rem', fontFamily: 'var(--font-mono)', fontWeight: 700,
              color: '#ff3b5c', padding: '2px 8px', borderRadius: 4,
              background: 'rgba(255,59,92,0.12)', border: '1px solid rgba(255,59,92,0.25)',
            }}>
              {coordRound!.revision_count} REVISION{coordRound!.revision_count > 1 ? 'S' : ''}
            </span>
          )}
          {/* Status badge */}
          <span style={{
            fontSize: '0.62rem', fontFamily: 'var(--font-mono)', fontWeight: 700,
            color: badge.color, padding: '2px 8px', borderRadius: 4,
            background: `${badge.color}18`, border: `1px solid ${badge.color}35`,
            ...(badge.pulse ? { animation: 'operational-pulse 2s infinite' } : {}),
          }}>
            {badge.label}
          </span>
        </div>
      </div>

      {/* KPI mini-row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: log.length > 0 ? 12 : 0 }}>
        <div style={{
          padding: '6px 10px', borderRadius: 6,
          background: 'rgba(0,163,255,0.06)', border: '1px solid rgba(0,163,255,0.15)',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#00a3ff' }}>
            {coordRound?.replan_count ?? 0}
          </div>
          <div style={{ fontSize: '0.6rem', color: 'rgba(140,180,220,0.45)' }}>Replan Cycles</div>
        </div>
        <div style={{
          padding: '6px 10px', borderRadius: 6,
          background: 'rgba(255,59,92,0.06)', border: '1px solid rgba(255,59,92,0.15)',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#ff3b5c' }}>
            {coordRound?.revision_count ?? 0}
          </div>
          <div style={{ fontSize: '0.6rem', color: 'rgba(140,180,220,0.45)' }}>Revisions</div>
        </div>
        <div style={{
          padding: '6px 10px', borderRadius: 6,
          background: `${badge.color}0a`, border: `1px solid ${badge.color}20`,
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: badge.color }}>
            {coordRound?.final_approval_round ?? '—'}
          </div>
          <div style={{ fontSize: '0.6rem', color: 'rgba(140,180,220,0.45)' }}>Approval Round</div>
        </div>
      </div>

      {/* Negotiation log */}
      {log.length > 0 && (
        <div style={{ maxHeight: 160, overflowY: 'auto' }}>
          {log.map((entry, i) => {
            const evt = EVENT_ICONS[entry.event] ?? { icon: '🔹', color: '#888' }
            const time = entry.timestamp
              ? new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
              : ''
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '4px 8px', borderRadius: 4,
                borderLeft: `2px solid ${evt.color}60`,
                marginBottom: 3,
                background: i === log.length - 1 ? `${evt.color}08` : 'transparent',
              }}>
                <span style={{ fontSize: '0.75rem' }}>{evt.icon}</span>
                <span style={{
                  fontSize: '0.6rem', fontFamily: 'var(--font-mono)', fontWeight: 700,
                  color: evt.color, minWidth: 130,
                }}>
                  {entry.event.replace(/_/g, ' ')}
                </span>
                <span style={{ fontSize: '0.6rem', color: 'rgba(160,200,240,0.5)', flex: 1 }}>
                  {entry.detail.slice(0, 60)}
                </span>
                <span style={{ fontSize: '0.55rem', fontFamily: 'var(--font-mono)', color: 'rgba(140,180,220,0.25)' }}>
                  {time}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const DEMO_MESSAGES: AgentMessage[] = [
  { incident_id: 'demo', sender: 'incident_commander', receiver: 'capacity_agent',   message_type: 'assignment',        content: 'Analyze ICU/ED capacity', timestamp: '' },
  { incident_id: 'demo', sender: 'capacity_agent',     receiver: 'staffing_agent',   message_type: 'capacity_alert',    content: 'ICU projected 104%', timestamp: '' },
  { incident_id: 'demo', sender: 'capacity_agent',     receiver: 'resource_agent',   message_type: 'occupancy_warning', content: 'Equipment demand spike', timestamp: '' },
  { incident_id: 'demo', sender: 'staffing_agent',     receiver: 'resource_agent',   message_type: 'staffing_gap',      content: '14-nurse gap, equip ICU', timestamp: '' },
  { incident_id: 'demo', sender: 'staffing_agent',     receiver: 'compliance_agent', message_type: 'staffing_request',  content: 'Ratio exception needed', timestamp: '' },
  { incident_id: 'demo', sender: 'resource_agent',     receiver: 'compliance_agent', message_type: 'resource_shortage', content: '3 ventilator deficit', timestamp: '' },
  { incident_id: 'demo', sender: 'compliance_agent',   receiver: 'incident_commander', message_type: 'policy_warning',  content: 'Conditionally compliant', timestamp: '' },
]

export function CollaborationDashboard() {
  const { selectedIncidentId, agentMessages, feedEvents, coordinationRounds } = useStore()

  const messages: AgentMessage[] = selectedIncidentId
    ? (agentMessages[selectedIncidentId] ?? [])
    : []

  const coordRound = selectedIncidentId ? (coordinationRounds[selectedIncidentId] ?? null) : null

  const isLive      = messages.length > 0
  const displayMsgs = isLive ? messages : DEMO_MESSAGES

  // Statistics
  const uniqueSenders   = new Set(displayMsgs.map(m => m.sender)).size
  const uniqueReceivers = new Set(displayMsgs.map(m => m.receiver)).size
  const activeAgents    = new Set([...displayMsgs.map(m => m.sender), ...displayMsgs.map(m => m.receiver)]).size
  const msgTypeBreakdown = displayMsgs.reduce<Record<string, number>>((acc, m) => {
    acc[m.message_type] = (acc[m.message_type] ?? 0) + 1
    return acc
  }, {})

  // Unique communication pairs
  const pairs = [...new Set(displayMsgs.map(m => `${m.sender}→${m.receiver}`))]

  return (
    <div className="card" style={{ borderColor: 'rgba(245,158,11,0.2)', background: 'rgba(245,158,11,0.02)' }}>
      <div className="card-header" style={{ marginBottom: 16 }}>
        <div className="card-title" style={{ color: '#f59e0b' }}>
          🤝 Multi-Agent Collaboration Dashboard
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {isLive && (
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#00e5a0', boxShadow: '0 0 8px #00e5a0', animation: 'operational-pulse 2s infinite' }} />
          )}
          <span className={`badge ${isLive ? 'badge-success' : 'badge-info'}`}>
            {isLive ? 'LIVE' : 'DEMO'}
          </span>
          <span className="badge badge-warning">{displayMsgs.length} messages</span>
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
        <StatCard label="Active Agents" value={activeAgents} sub="coordinating" color="#00a3ff" />
        <StatCard label="Messages Exchanged" value={displayMsgs.length} sub="inter-agent" color="#f59e0b" />
        <StatCard label="Communication Pairs" value={pairs.length} sub="unique channels" color="#a78bfa" />
        <StatCard label="Coordination Rounds" value={coordRound?.current_round ?? 1} sub={`max ${coordRound?.max_rounds ?? 3} rounds`} color="#00e5a0" />
      </div>

      {/* Phase 19A: Negotiation Status Panel */}
      <NegotiationStatusPanel coordRound={coordRound} />

      {/* Graph + breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        {/* Communication graph */}
        <div style={{
          background: 'rgba(0,0,0,0.15)', borderRadius: 10,
          border: '1px solid rgba(255,255,255,0.06)',
          padding: '12px',
          display: 'flex', flexDirection: 'column', alignItems: 'center',
        }}>
          <div style={{ fontSize: '0.7rem', color: 'rgba(160,200,240,0.5)', marginBottom: 8, fontWeight: 700, letterSpacing: 1 }}>
            COMMUNICATION GRAPH
          </div>
          <CommunicationGraph messages={displayMsgs} />
          <div style={{ fontSize: '0.62rem', color: 'rgba(140,180,220,0.3)', marginTop: 6 }}>
            Edge labels = message count • Arrow width = frequency
          </div>
        </div>

        {/* Message type breakdown */}
        <div style={{
          background: 'rgba(0,0,0,0.15)', borderRadius: 10,
          border: '1px solid rgba(255,255,255,0.06)',
          padding: '12px',
        }}>
          <div style={{ fontSize: '0.7rem', color: 'rgba(160,200,240,0.5)', marginBottom: 10, fontWeight: 700, letterSpacing: 1 }}>
            MESSAGE TYPE BREAKDOWN
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Object.entries(msgTypeBreakdown).map(([type, count]) => {
              const color = MSG_TYPE_COLORS[type] ?? '#888'
              const maxCount = Math.max(...Object.values(msgTypeBreakdown))
              return (
                <div key={type}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ fontSize: '0.68rem', color, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                      {type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                    <span style={{ fontSize: '0.68rem', color: 'rgba(160,200,240,0.5)' }}>{count}</span>
                  </div>
                  <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>
                    <div style={{
                      height: '100%',
                      width: `${(count / maxCount) * 100}%`,
                      background: color,
                      borderRadius: 2,
                      opacity: 0.7,
                    }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Agent relationships */}
      <div style={{
        background: 'rgba(0,0,0,0.1)', borderRadius: 10,
        border: '1px solid rgba(255,255,255,0.05)',
        padding: '12px',
      }}>
        <div style={{ fontSize: '0.7rem', color: 'rgba(160,200,240,0.5)', marginBottom: 8, fontWeight: 700, letterSpacing: 1 }}>
          AGENT RELATIONSHIPS
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {pairs.map((pair, i) => {
            const [from, to] = pair.split('→')
            const fromNode = getNode(from)
            const toNode   = getNode(to)
            const pairMsgs = displayMsgs.filter(m => m.sender === from && m.receiver === to)
            const latestType = pairMsgs[pairMsgs.length - 1]?.message_type
            const edgeColor = MSG_TYPE_COLORS[latestType ?? ''] ?? '#666'
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '5px 10px', borderRadius: 20,
                background: `${edgeColor}0d`,
                border: `1px solid ${edgeColor}25`,
                fontSize: '0.68rem',
              }}>
                <span style={{ color: fromNode?.color ?? '#888' }}>{fromNode?.icon} {fromNode?.label}</span>
                <span style={{ color: edgeColor, fontWeight: 700 }}>→</span>
                <span style={{ color: toNode?.color ?? '#888' }}>{toNode?.icon} {toNode?.label}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: edgeColor }}>×{pairMsgs.length}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
