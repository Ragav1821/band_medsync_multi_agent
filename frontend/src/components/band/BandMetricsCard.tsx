/**
 * BandMetricsCard.tsx
 * ─────────────────────────────────────────────────────────────────────────
 * Standalone dashboard card showing Band coordination metrics.
 * Derived entirely from existing Zustand store — zero backend dependencies.
 *
 * Props (all optional):
 *   onNavigate — called when "View Band Hub →" is clicked
 */

import { useStore } from '../../store/appStore'
import type { AgentLiveState, WSAgentEvent } from '../../store/appStore'
import type { Incident } from '../../api/client'

interface BandMetricsCardProps {
  onNavigate?: (page: string) => void
}

// ── Derived metric helpers ────────────────────────────────────────────────

/** Count how many distinct Band rooms have been activated (one per incident that has run agents) */
function countBandRooms(agentStates: Record<string, AgentLiveState[]>): number {
  return Object.values(agentStates).filter(
    (agents) => agents.some((a) => a.status !== 'idle')
  ).length
}

/** Count how many agents across ALL rooms are currently active/thinking/completed */
function countActiveAgents(agentStates: Record<string, AgentLiveState[]>): number {
  return Object.values(agentStates).flat().filter(
    (a) => a.status === 'active' || a.status === 'thinking' || a.status === 'completed'
  ).length
}

/** Count total agent:* events as a proxy for "messages routed through Band" */
function countMessagesRouted(feedEvents: WSAgentEvent[]): number {
  return feedEvents.filter((e) => e.event_type?.startsWith('agent:')).length
}

/** Count incidents that are not resolved */
function countActiveIncidents(incidents: Incident[]): number {
  return incidents.filter((i) => i.status !== 'resolved').length
}

// ── Stat cell ─────────────────────────────────────────────────────────────

interface StatCellProps {
  label: string
  value: string | number
  color: string
  icon: string
  pulse?: boolean
}

function StatCell({ label, value, color, icon, pulse }: StatCellProps) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 6,
      padding: '12px 14px', borderRadius: 10,
      background: 'rgba(0,0,0,0.18)',
      border: `1px solid ${color}22`,
      flex: 1, minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: '0.9rem' }}>{icon}</span>
        {pulse && (
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: color,
            boxShadow: `0 0 6px ${color}`,
            animation: 'operational-pulse 1.8s infinite',
            flexShrink: 0,
          }} />
        )}
      </div>
      <div style={{
        fontSize: '1.6rem', fontWeight: 800, color, lineHeight: 1,
        letterSpacing: '-0.03em',
      }}>
        {value}
      </div>
      <div style={{
        fontSize: '0.65rem', color: 'rgba(140,180,220,0.45)',
        fontFamily: 'var(--font-mono)', lineHeight: 1.3,
        textTransform: 'uppercase', letterSpacing: '0.05em',
      }}>
        {label}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

export function BandMetricsCard({ onNavigate }: BandMetricsCardProps) {
  const { agentStates, feedEvents, incidents, selectedIncidentId } = useStore()

  const bandRoomsActive   = countBandRooms(agentStates)
  const agentsCoordinating = countActiveAgents(agentStates)
  const messagesRouted    = countMessagesRouted(feedEvents)
  const incidentsActive   = countActiveIncidents(incidents)

  const hasLiveRoom = bandRoomsActive > 0
  const currentRoomId = selectedIncidentId
    ? `BR-${selectedIncidentId.slice(0, 6).toUpperCase()}`
    : null

  return (
    <div className="card" style={{
      borderColor: hasLiveRoom ? 'rgba(0,163,255,0.3)' : 'rgba(0,163,255,0.12)',
      background: 'rgba(0,163,255,0.03)',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Animated scan line when a room is active */}
      {hasLiveRoom && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: 'linear-gradient(90deg, transparent, #00a3ff80, transparent)',
          animation: 'scan-line 3s linear infinite',
        }} />
      )}

      {/* ── Header ───────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{ fontSize: '1.1rem' }}>📡</div>
        <div style={{ flex: 1 }}>
          <div style={{
            fontSize: '0.78rem', fontWeight: 700, color: '#00a3ff',
            letterSpacing: '0.07em', textTransform: 'uppercase',
          }}>
            Band Coordination
          </div>
          {currentRoomId && (
            <div style={{
              fontSize: '0.6rem', color: 'rgba(140,180,220,0.4)',
              fontFamily: 'var(--font-mono)', marginTop: 1,
            }}>
              Active room: {currentRoomId}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {hasLiveRoom && (
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: '#00e5a0', boxShadow: '0 0 8px #00e5a0',
              animation: 'operational-pulse 2s infinite',
            }} />
          )}
          <span className={`badge ${hasLiveRoom ? 'badge-success' : 'badge-info'}`}
            style={{ fontSize: '0.6rem' }}>
            {hasLiveRoom ? 'LIVE' : 'STANDBY'}
          </span>
        </div>
      </div>

      {/* ── 4 metric cells ───────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <StatCell
          icon="🏠"
          label="Band Rooms Active"
          value={bandRoomsActive}
          color="#00a3ff"
          pulse={hasLiveRoom}
        />
        <StatCell
          icon="🤖"
          label="Agents Coordinating"
          value={agentsCoordinating}
          color="#00e5a0"
          pulse={agentsCoordinating > 0}
        />
        <StatCell
          icon="💬"
          label="Messages Routed"
          value={messagesRouted}
          color="#f59e0b"
        />
        <StatCell
          icon="🚨"
          label="Incidents Active"
          value={incidentsActive}
          color={incidentsActive > 0 ? '#ff3b5c' : '#00e5a0'}
        />
      </div>

      {/* ── Footer nav link ───────────────────────────────── */}
      {onNavigate && (
        <button
          onClick={() => onNavigate('agents')}
          className="btn btn-ghost btn-sm"
          style={{ marginTop: 14, width: '100%', justifyContent: 'center' }}
        >
          View Band Hub →
        </button>
      )}
    </div>
  )
}
