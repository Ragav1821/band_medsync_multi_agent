import { useEffect, useState } from 'react'
import { useStore } from '../../store/appStore'

interface BandPhase {
  id: string
  icon: string
  label: string
  sublabel: string
  color: string
  timestamp?: string
  active: boolean
  done: boolean
  messageCount?: number
  agents?: string[]
}

const AGENT_COLORS: Record<string, string> = {
  incident_commander: '#00a3ff',
  capacity_agent: '#00e5a0',
  staffing_agent: '#f59e0b',
  resource_agent: '#a78bfa',
  compliance_agent: '#fb923c',
}

const AGENT_ICONS: Record<string, string> = {
  incident_commander: '🎯',
  capacity_agent: '🏥',
  staffing_agent: '👩‍⚕️',
  resource_agent: '📦',
  compliance_agent: '⚖️',
}

const AGENT_SHORT: Record<string, string> = {
  incident_commander: 'CMD',
  capacity_agent: 'CAP',
  staffing_agent: 'STF',
  resource_agent: 'RES',
  compliance_agent: 'CPL',
}

export function BandRoomPanel() {
  const { selectedIncidentId, agentStates, feedEvents } = useStore()
  const [pulseIndex, setPulseIndex] = useState(0)
  const [msgCount, setMsgCount] = useState(0)

  const currentAgents = selectedIncidentId ? (agentStates[selectedIncidentId] ?? []) : []
  const currentFeed = feedEvents.filter(e => !selectedIncidentId || e.incident_id === selectedIncidentId)

  const activeAgents = currentAgents.filter(a => a.status !== 'idle')
  const completedAgents = currentAgents.filter(a => a.status === 'completed')
  const hasCompliance = completedAgents.some(a => a.name === 'compliance_agent')
  const hasPlan = currentFeed.some(e => e.event_type === 'plan:ready')
  const hasApproval = currentFeed.some(e => e.event_type === 'approval' || e.event_type === 'plan_approved')
  const hasStarted = activeAgents.length > 0 || completedAgents.length > 0

  // Running message count from feed
  useEffect(() => {
    setMsgCount(currentFeed.filter(e => e.event_type?.startsWith('agent:')).length)
  }, [currentFeed.length])

  // Pulse through active steps
  useEffect(() => {
    const t = setInterval(() => setPulseIndex(p => p + 1), 1200)
    return () => clearInterval(t)
  }, [])

  const bandRoomId = selectedIncidentId
    ? `BR-${selectedIncidentId.slice(0, 6).toUpperCase()}`
    : 'BR-STANDBY'

  const phases: BandPhase[] = [
    {
      id: 'created',
      icon: '📡',
      label: 'Band Room Created',
      sublabel: `Room ${bandRoomId}`,
      color: '#00a3ff',
      active: hasStarted,
      done: hasStarted,
      timestamp: hasStarted ? new Date().toLocaleTimeString() : undefined,
    },
    {
      id: 'joined',
      icon: '🤝',
      label: 'Agents Joined',
      sublabel: `${activeAgents.length + completedAgents.length}/5 agents`,
      color: '#00e5a0',
      active: hasStarted && activeAgents.length > 0,
      done: completedAgents.length >= 3,
      agents: [...activeAgents, ...completedAgents].map(a => a.name),
    },
    {
      id: 'messages',
      icon: '💬',
      label: 'Messages Exchanged',
      sublabel: `${msgCount} coordination events`,
      color: '#f59e0b',
      active: msgCount > 0,
      done: msgCount > 5,
      messageCount: msgCount,
    },
    {
      id: 'context',
      icon: '🧠',
      label: 'Context Shared',
      sublabel: 'Gemini synthesis active',
      color: '#a78bfa',
      active: completedAgents.length >= 2,
      done: completedAgents.length >= 4,
    },
    {
      id: 'compliance',
      icon: '⚖️',
      label: 'Compliance Review',
      sublabel: 'EMTALA & regulatory check',
      color: '#fb923c',
      active: hasCompliance,
      done: hasCompliance,
    },
    {
      id: 'approval',
      icon: '✅',
      label: 'Human Approval',
      sublabel: hasPlan ? 'Plan awaiting sign-off' : 'Pending plan generation',
      color: '#00e5a0',
      active: hasPlan,
      done: hasApproval,
    },
  ]

  const activePhaseIndex = phases.reduce((last, p, i) => (p.active || p.done ? i : last), -1)

  if (!selectedIncidentId) {
    return (
      <div className="card" style={{ borderColor: 'rgba(0,163,255,0.2)', background: 'rgba(0,163,255,0.03)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div style={{ fontSize: '1.4rem' }}>📡</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#00a3ff', letterSpacing: '0.06em' }}>
              BAND COORDINATION ROOM
            </div>
            <div style={{ fontSize: '0.68rem', color: 'rgba(140,180,220,0.4)', fontFamily: 'var(--font-mono)' }}>
              Awaiting incident activation
            </div>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <span className="badge badge-info">STANDBY</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {['Band Room', 'Agent Mesh', 'Context Bus', 'Compliance Layer', 'Human Gate'].map(label => (
            <div key={label} style={{
              padding: '4px 10px', borderRadius: 20, fontSize: '0.65rem',
              background: 'rgba(255,255,255,0.04)', border: '1px solid var(--color-border)',
              color: 'rgba(140,180,220,0.4)',
            }}>{label}</div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="card" style={{ borderColor: 'rgba(0,163,255,0.25)', background: 'rgba(0,163,255,0.03)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: 'linear-gradient(135deg, rgba(0,163,255,0.3), rgba(124,58,237,0.3))',
          border: '1px solid rgba(0,163,255,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem',
          boxShadow: '0 0 16px rgba(0,163,255,0.25)',
        }}>📡</div>
        <div>
          <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#00a3ff', letterSpacing: '0.06em' }}>
            BAND COORDINATION ROOM
          </div>
          <div style={{ fontSize: '0.68rem', color: 'rgba(140,180,220,0.4)', fontFamily: 'var(--font-mono)' }}>
            {bandRoomId} · {hasStarted ? 'ACTIVE' : 'INITIALIZING'}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
          {hasStarted && (
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: '#00e5a0',
              boxShadow: '0 0 8px #00e5a0',
              animation: 'operational-pulse 2s infinite',
            }} />
          )}
          <span className={`badge ${hasStarted ? 'badge-success' : 'badge-info'}`}>
            {hasStarted ? 'LIVE' : 'READY'}
          </span>
        </div>
      </div>

      {/* Agent Mesh */}
      {hasStarted && (
        <div style={{ marginBottom: 16, padding: '10px 12px', background: 'rgba(0,0,0,0.2)', borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.4)', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
            AGENT MESH — {activeAgents.length + completedAgents.length} CONNECTED
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(AGENT_ICONS).map(([name, icon]) => {
              const agent = currentAgents.find(a => a.name === name)
              const status = agent?.status ?? 'idle'
              const color = AGENT_COLORS[name]
              const isActive = status === 'active' || status === 'thinking'
              const isDone = status === 'completed'
              return (
                <div key={name} style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '4px 9px', borderRadius: 20,
                  background: isDone ? `${color}18` : isActive ? `${color}12` : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${isDone ? `${color}55` : isActive ? `${color}40` : 'rgba(255,255,255,0.07)'}`,
                  transition: 'all 0.4s ease',
                  boxShadow: isActive ? `0 0 10px ${color}30` : 'none',
                }}>
                  <span style={{ fontSize: '0.75rem' }}>{icon}</span>
                  <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: isDone ? color : isActive ? color : 'rgba(140,180,220,0.3)' }}>
                    {AGENT_SHORT[name]}
                  </span>
                  {isDone && <span style={{ fontSize: '0.6rem', color }}>✓</span>}
                  {isActive && (
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: color, animation: 'operational-pulse 1s infinite', boxShadow: `0 0 6px ${color}` }} />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Phase Timeline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {phases.map((phase, i) => {
          const isCurrentlyActive = i === activePhaseIndex && !phase.done
          const shouldPulse = isCurrentlyActive && (pulseIndex % 2 === 0)

          return (
            <div key={phase.id} style={{ display: 'flex', gap: 0, position: 'relative' }}>
              {/* Connector line */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 32, flexShrink: 0 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  background: phase.done
                    ? `${phase.color}25`
                    : isCurrentlyActive
                      ? `${phase.color}15`
                      : 'rgba(255,255,255,0.04)',
                  border: `2px solid ${phase.done ? phase.color : isCurrentlyActive ? `${phase.color}80` : 'rgba(255,255,255,0.1)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.85rem',
                  boxShadow: phase.done ? `0 0 12px ${phase.color}40` : isCurrentlyActive ? `0 0 8px ${phase.color}30` : 'none',
                  transition: 'all 0.5s ease',
                  zIndex: 1,
                }}>
                  {phase.done ? '✓' : phase.icon}
                </div>
                {i < phases.length - 1 && (
                  <div style={{
                    width: 2, flex: 1, minHeight: 20,
                    background: phase.done
                      ? `linear-gradient(to bottom, ${phase.color}60, ${phases[i + 1].color}30)`
                      : 'rgba(255,255,255,0.06)',
                    transition: 'background 0.5s ease',
                  }} />
                )}
              </div>

              {/* Content */}
              <div style={{ flex: 1, paddingLeft: 12, paddingBottom: i < phases.length - 1 ? 14 : 0, paddingTop: 2 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    fontSize: '0.78rem', fontWeight: 600,
                    color: phase.done ? phase.color : isCurrentlyActive ? `${phase.color}cc` : 'rgba(140,180,220,0.35)',
                    transition: 'color 0.4s ease',
                  }}>
                    {phase.label}
                  </div>
                  {isCurrentlyActive && (
                    <div style={{
                      width: 5, height: 5, borderRadius: '50%', background: phase.color,
                      boxShadow: `0 0 8px ${phase.color}`,
                      opacity: shouldPulse ? 1 : 0.4, transition: 'opacity 0.6s ease',
                    }} />
                  )}
                  {phase.done && (
                    <span style={{ fontSize: '0.6rem', color: phase.color, fontFamily: 'var(--font-mono)', opacity: 0.7 }}>
                      COMPLETE
                    </span>
                  )}
                </div>
                <div style={{
                  fontSize: '0.65rem', fontFamily: 'var(--font-mono)',
                  color: phase.done ? 'rgba(140,180,220,0.5)' : 'rgba(140,180,220,0.25)',
                  marginTop: 1,
                }}>
                  {phase.sublabel}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Message throughput footer */}
      {msgCount > 0 && (
        <div style={{
          marginTop: 16, padding: '8px 12px',
          background: 'rgba(0,0,0,0.15)',
          borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.4)', fontFamily: 'var(--font-mono)' }}>
            BAND THROUGHPUT
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#00a3ff', lineHeight: 1 }}>{msgCount}</div>
              <div style={{ fontSize: '0.55rem', color: 'rgba(140,180,220,0.3)', marginTop: 2 }}>EVENTS</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#00e5a0', lineHeight: 1 }}>{completedAgents.length}</div>
              <div style={{ fontSize: '0.55rem', color: 'rgba(140,180,220,0.3)', marginTop: 2 }}>COMPLETE</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1rem', fontWeight: 800, color: '#a78bfa', lineHeight: 1 }}>
                {completedAgents.length > 0 ? `${Math.round((completedAgents.reduce((s, a) => s + (a.confidence ?? 0.88), 0) / completedAgents.length) * 100)}%` : '—'}
              </div>
              <div style={{ fontSize: '0.55rem', color: 'rgba(140,180,220,0.3)', marginTop: 2 }}>CONF</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
