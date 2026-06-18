import { useEffect, useState } from 'react'
import { useStore } from '../../store/appStore'

// ── Agent roster ─────────────────────────────────────────────
const AGENTS = [
  { key: 'incident_commander', icon: '🎯', label: 'Commander',  color: '#00a3ff', short: 'CMD' },
  { key: 'capacity_agent',     icon: '🏥', label: 'Capacity',   color: '#00e5a0', short: 'CAP' },
  { key: 'staffing_agent',     icon: '👩‍⚕️', label: 'Staffing',  color: '#f59e0b', short: 'STF' },
  { key: 'resource_agent',     icon: '📦', label: 'Resource',   color: '#a78bfa', short: 'RES' },
  { key: 'compliance_agent',   icon: '⚖️', label: 'Compliance', color: '#fb923c', short: 'CPL' },
]

// Workflow stage derived from live state
function deriveStage(
  completedCount: number,
  hasPlan: boolean,
  hasApproval: boolean,
  msgCount: number,
): { label: string; color: string } {
  if (hasApproval)            return { label: 'Plan Approved',       color: '#00e5a0' }
  if (hasPlan)                return { label: 'Awaiting Approval',   color: '#a78bfa' }
  if (completedCount >= 4)    return { label: 'Synthesizing Plan',   color: '#00a3ff' }
  if (completedCount >= 3)    return { label: 'Compliance Check',    color: '#fb923c' }
  if (completedCount >= 1)    return { label: 'Agents Reporting',    color: '#f59e0b' }
  if (msgCount > 0)           return { label: 'Analysis Running',    color: '#00a3ff' }
  return                             { label: 'Initializing Room',   color: '#4b5563' }
}

export function BandRoomPanel() {
  const { selectedIncidentId, agentStates, feedEvents, bandRooms } = useStore()
  const [tick, setTick]       = useState(0)
  const [msgCount, setMsgCount] = useState(0)

  // Heartbeat for live pulse animations
  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(t)
  }, [])

  const currentAgents = selectedIncidentId ? (agentStates[selectedIncidentId] ?? []) : []
  const currentFeed   = feedEvents.filter(
    e => !selectedIncidentId || e.incident_id === selectedIncidentId
  )

  // ── Derived state ──────────────────────────────────────────
  const connectedAgents  = currentAgents.filter(a => a.status !== 'idle')
  const completedAgents  = currentAgents.filter(a => a.status === 'completed')
  const activeAgents     = currentAgents.filter(a => a.status === 'active' || a.status === 'thinking')
  const hasPlan          = currentFeed.some(e => e.event_type === 'plan:ready')
  const hasApproval      = currentFeed.some(e => e.event_type === 'approval' || e.event_type === 'plan_approved')
  const hasStarted       = connectedAgents.length > 0

  useEffect(() => {
    setMsgCount(currentFeed.filter(e => e.event_type?.startsWith('agent:')).length)
  }, [currentFeed.length])

  // Real Band chat_id from store (set when room is created via WS event)
  const bandChatId = selectedIncidentId ? (bandRooms[selectedIncidentId] ?? null) : null
  const bandRoomId = bandChatId
    ? `LIVE-${bandChatId.slice(0, 8).toUpperCase()}`
    : selectedIncidentId
      ? `BR-${selectedIncidentId.slice(0, 6).toUpperCase()}`
      : 'BR-STANDBY'
  const bandRoomUrl = bandChatId ? `https://app.band.ai/chats/${bandChatId}` : null

  const isActive = hasStarted && !hasApproval
  const stage    = deriveStage(completedAgents.length, hasPlan, hasApproval, msgCount)

  // Blinking dot cycle
  const pulsing  = tick % 2 === 0

  // ── STANDBY (no incident) ──────────────────────────────────
  if (!selectedIncidentId) {
    return (
      <div className="card" style={{ borderColor: 'rgba(0,163,255,0.18)', background: 'rgba(0,163,255,0.03)' }}>
        <BandRoomHeader roomId="BR-STANDBY" status="STANDBY" statusColor="#4b5563" />
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          gap: 10, marginBottom: 16,
        }}>
          <InfoCell label="Agents Connected" value="0 / 5" />
          <InfoCell label="Messages Routed"  value="0"     />
          <InfoCell label="Workflow Stage"   value="Idle"  colSpan />
        </div>
        <ParticipantList agents={[]} currentAgents={[]} />
      </div>
    )
  }

  // ── ACTIVE ─────────────────────────────────────────────────
  return (
    <div className="card" style={{
      borderColor: isActive ? 'rgba(0,163,255,0.35)' : hasApproval ? 'rgba(0,229,160,0.35)' : 'rgba(0,163,255,0.2)',
      background: 'rgba(0,163,255,0.03)',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Animated top-border glow when active */}
      {isActive && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: 'linear-gradient(90deg, transparent, #00a3ff, transparent)',
          animation: 'scan-line 2s linear infinite',
        }} />
      )}

      <BandRoomHeader
        roomId={bandRoomId}
        status={hasApproval ? 'COMPLETE' : bandChatId ? 'LIVE' : isActive ? 'ACTIVE' : 'READY'}
        statusColor={hasApproval ? '#00e5a0' : bandChatId ? '#00ff88' : isActive ? '#00a3ff' : '#00e5a0'}
        pulsing={(isActive || !!bandChatId) && pulsing}
      />

      {/* ── Band Room Live Link ─────────────────────────────── */}
      {bandRoomUrl && (
        <a
          href={bandRoomUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            marginBottom: 10,
            padding: '6px 10px',
            background: 'rgba(0,255,136,0.08)',
            border: '1px solid rgba(0,255,136,0.3)',
            borderRadius: 8,
            color: '#00ff88',
            fontSize: 11,
            fontFamily: 'monospace',
            textDecoration: 'none',
            cursor: 'pointer',
          }}
        >
          <span style={{ fontSize: 14 }}>📡</span>
          <span style={{ flex: 1 }}>
            Band Room: <b>{bandChatId!.slice(0, 8).toUpperCase()}</b>
          </span>
          <span style={{ opacity: 0.7 }}>Open in Band ↗</span>
        </a>
      )}

      {/* ── Key metrics row ───────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
        <InfoCell
          label="Agents Connected"
          value={`${connectedAgents.length} / 5`}
          color={connectedAgents.length === 5 ? '#00e5a0' : '#00a3ff'}
        />
        <InfoCell
          label="Messages Routed"
          value={String(msgCount)}
          color="#f59e0b"
        />
        <InfoCell
          label="Workflow Stage"
          value={stage.label}
          color={stage.color}
          small
        />
      </div>

      {/* ── Participants ──────────────────────────────────── */}
      <ParticipantList agents={AGENTS} currentAgents={currentAgents} />

      {/* ── Throughput footer ─────────────────────────────── */}
      {msgCount > 0 && (
        <div style={{
          marginTop: 12,
          padding: '8px 12px',
          background: 'rgba(0,0,0,0.18)',
          borderRadius: 8,
          border: '1px solid rgba(255,255,255,0.05)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: '0.62rem', color: 'rgba(140,180,220,0.4)', fontFamily: 'var(--font-mono)' }}>
            BAND THROUGHPUT
          </span>
          <div style={{ display: 'flex', gap: 18 }}>
            <Stat value={msgCount}              label="EVENTS"   color="#00a3ff" />
            <Stat value={completedAgents.length} label="DONE"     color="#00e5a0" />
            <Stat
              value={completedAgents.length > 0
                ? `${Math.round((completedAgents.reduce((s, a) => s + (a.confidence ?? 0.88), 0) / completedAgents.length) * 100)}%`
                : '—'}
              label="CONF"
              color="#a78bfa"
            />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────

function BandRoomHeader({
  roomId, status, statusColor, pulsing = false,
}: {
  roomId: string; status: string; statusColor: string; pulsing?: boolean
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
      <div style={{
        width: 38, height: 38, borderRadius: 10, flexShrink: 0,
        background: 'linear-gradient(135deg, rgba(0,163,255,0.25), rgba(124,58,237,0.25))',
        border: '1px solid rgba(0,163,255,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem',
        boxShadow: '0 0 14px rgba(0,163,255,0.2)',
      }}>📡</div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#00a3ff', letterSpacing: '0.07em', lineHeight: 1.2 }}>
          BAND COORDINATION ROOM
        </div>
        <div style={{ fontSize: '0.66rem', color: 'rgba(140,180,220,0.45)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
          Room ID: {roomId}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        {pulsing && (
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: statusColor,
            boxShadow: `0 0 8px ${statusColor}`,
            opacity: pulsing ? 1 : 0.3,
            transition: 'opacity 0.5s ease',
          }} />
        )}
        <div style={{
          padding: '3px 10px', borderRadius: 20, fontSize: '0.65rem', fontWeight: 700,
          background: `${statusColor}18`, border: `1px solid ${statusColor}50`,
          color: statusColor, fontFamily: 'var(--font-mono)', letterSpacing: '0.05em',
        }}>
          {status}
        </div>
      </div>
    </div>
  )
}

function InfoCell({
  label, value, color, colSpan, small,
}: {
  label: string; value: string; color?: string; colSpan?: boolean; small?: boolean
}) {
  return (
    <div style={{
      gridColumn: colSpan ? '1 / -1' : undefined,
      padding: '9px 12px', borderRadius: 8,
      background: 'rgba(0,0,0,0.18)',
      border: '1px solid rgba(255,255,255,0.05)',
    }}>
      <div style={{ fontSize: '0.58rem', color: 'rgba(140,180,220,0.35)', fontFamily: 'var(--font-mono)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{
        fontWeight: 800,
        fontSize: small ? '0.75rem' : '1.05rem',
        color: color ?? 'rgba(200,230,255,0.9)',
        lineHeight: 1,
        wordBreak: 'break-word',
      }}>
        {value}
      </div>
    </div>
  )
}

function ParticipantList({
  agents,
  currentAgents,
}: {
  agents: typeof AGENTS;
  currentAgents: ReturnType<typeof useStore>['agentStates'][string]
}) {
  const isEmpty = agents.length === 0

  return (
    <div style={{
      padding: '10px 12px', borderRadius: 8,
      background: 'rgba(0,0,0,0.15)',
      border: '1px solid rgba(255,255,255,0.05)',
    }}>
      <div style={{ fontSize: '0.58rem', color: 'rgba(140,180,220,0.35)', fontFamily: 'var(--font-mono)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Participants
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {isEmpty
          ? AGENTS.map(a => (
              <ParticipantRow key={a.key} agent={a} status="idle" />
            ))
          : agents.map(a => {
              const live = currentAgents?.find(la => la.name === a.key)
              return (
                <ParticipantRow
                  key={a.key}
                  agent={a}
                  status={live?.status ?? 'idle'}
                  confidence={live?.confidence}
                  summary={live?.summary}
                />
              )
            })
        }
      </div>
    </div>
  )
}

function ParticipantRow({
  agent, status, confidence, summary,
}: {
  agent: typeof AGENTS[0]
  status: 'idle' | 'active' | 'thinking' | 'completed' | 'error'
  confidence?: number
  summary?: string
}) {
  const isActive   = status === 'active' || status === 'thinking'
  const isComplete = status === 'completed'
  const color      = isActive || isComplete ? agent.color : 'rgba(140,180,220,0.2)'

  const statusDot = isComplete ? '✓' : isActive ? '⬤' : '○'
  const statusLabel = isComplete ? 'Done' : isActive ? (status === 'thinking' ? 'Thinking…' : 'Running') : 'Standby'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '5px 8px', borderRadius: 7,
      background: isComplete ? `${agent.color}10` : isActive ? `${agent.color}08` : 'transparent',
      border: `1px solid ${isActive || isComplete ? `${agent.color}30` : 'transparent'}`,
      transition: 'all 0.4s ease',
    }}>
      <span style={{ fontSize: '1rem', lineHeight: 1, width: 20, textAlign: 'center', flexShrink: 0 }}>{agent.icon}</span>
      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isActive || isComplete ? 'rgba(220,240,255,0.9)' : 'rgba(140,180,220,0.35)', flex: 1 }}>
        {agent.label}
      </span>
      {isComplete && confidence !== undefined && (
        <span style={{ fontSize: '0.62rem', color: agent.color, fontFamily: 'var(--font-mono)' }}>
          {Math.round(confidence * 100)}%
        </span>
      )}
      <span style={{
        fontSize: '0.62rem', fontFamily: 'var(--font-mono)',
        color: isComplete ? agent.color : isActive ? agent.color : 'rgba(100,130,160,0.3)',
        flexShrink: 0,
      }}>
        {statusDot} {statusLabel}
      </span>
    </div>
  )
}

function Stat({ value, label, color }: { value: string | number; label: string; color: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '1rem', fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: '0.52rem', color: 'rgba(140,180,220,0.3)', marginTop: 3 }}>{label}</div>
    </div>
  )
}
