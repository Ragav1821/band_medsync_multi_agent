import { useEffect, useState } from 'react'
import { useStore, type AgentLiveState } from '../store/appStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { BandRoomPanel } from '../components/band/BandRoomPanel'
import { CollaborationTimeline } from '../components/band/CollaborationTimeline'

const AGENT_META: Record<string, { icon: string; className: string; fullName: string; role: string; color: string }> = {
  incident_commander: { icon: '🎯', className: 'commander', fullName: 'Incident Commander', role: 'Master Orchestrator', color: 'var(--agent-commander)' },
  capacity_agent: { icon: '🏥', className: 'capacity', fullName: 'Capacity Agent', role: 'Hospital Capacity Analysis', color: 'var(--agent-capacity)' },
  staffing_agent: { icon: '👩‍⚕️', className: 'staffing', fullName: 'Staffing Agent', role: 'Nurse Allocation', color: 'var(--agent-staffing)' },
  resource_agent: { icon: '📦', className: 'resource', fullName: 'Resource Agent', role: 'Equipment & Supplies', color: 'var(--agent-resource)' },
  compliance_agent: { icon: '⚖️', className: 'compliance', fullName: 'Compliance Agent', role: 'EMTALA & Regulations', color: 'var(--agent-compliance)' },
}

export function AgentActivity({ onNavigate }: { onNavigate: (page: string, id?: string) => void }) {
  const { selectedIncidentId, agentStates, feedEvents, incidents } = useStore()
  const [activeTab, setActiveTab] = useState<'overview' | 'feed' | 'band'>('band')

  useWebSocket(selectedIncidentId)

  const currentAgents = selectedIncidentId ? (agentStates[selectedIncidentId] ?? []) : []
  const currentFeed = feedEvents.filter(e => !selectedIncidentId || e.incident_id === selectedIncidentId)

  const selectedIncident = incidents.find(i => i.id === selectedIncidentId)

  const completedCount = currentAgents.filter(a => a.status === 'completed').length
  const totalAgents = 5

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 className="page-title">📡 Band Coordination Hub</h1>
            <p className="page-subtitle">Real-time multi-agent collaboration via Band coordination room</p>
          </div>
          {selectedIncidentId && (
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('action-plan', selectedIncidentId)}>
                📋 View Action Plan
              </button>
            </div>
          )}
        </div>
      </div>

      {!selectedIncidentId ? (
        <div>
          {/* Band standby + empty state together */}
          <div className="grid-2" style={{ marginBottom: 'var(--spacing-lg)' }}>
            <BandRoomPanel />
            <div className="card empty-state">
              <div className="empty-state-icon">📡</div>
              <div className="empty-state-title">No incident selected</div>
              <div className="empty-state-sub">Create or select an incident to activate a Band coordination room</div>
              <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => onNavigate('incidents')}>
                🚨 Create Incident →
              </button>
            </div>
          </div>
          {/* Show demo timeline regardless */}
          <CollaborationTimeline />
        </div>
      ) : (
        <>
          {/* Incident Banner */}
          {selectedIncident && (
            <div style={{ background: 'rgba(255,59,92,0.08)', border: '1px solid rgba(255,59,92,0.2)', borderRadius: 'var(--radius-md)', padding: 'var(--spacing-md) var(--spacing-lg)', marginBottom: 'var(--spacing-lg)', display: 'flex', gap: 'var(--spacing-lg)', alignItems: 'center' }}>
              <span className="badge badge-critical">LEVEL {selectedIncident.severity_level} CRITICAL</span>
              <span style={{ color: 'white', fontWeight: 600 }}>Mass Casualty Event · {selectedIncident.incoming_patients} incoming patients · ICU {selectedIncident.icu_occupancy_pct}%</span>
              <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'rgba(140,180,220,0.4)' }}>{selectedIncidentId.slice(0, 8)}</span>
            </div>
          )}

          {/* Overall Progress */}
          <div className="card" style={{ marginBottom: 'var(--spacing-lg)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-md)' }}>
              <div className="card-title">Workflow Progress</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--color-accent)' }}>
                {completedCount}/{totalAgents} agents complete
              </div>
            </div>
            <div style={{ height: 6, background: 'rgba(255,255,255,0.05)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${(completedCount / totalAgents) * 100}%`,
                background: completedCount === totalAgents
                  ? 'linear-gradient(90deg, var(--color-success), #00b36e)'
                  : 'linear-gradient(90deg, var(--color-accent), #0062ff)',
                borderRadius: 'var(--radius-full)',
                transition: 'width 0.8s ease',
                boxShadow: '0 0 12px rgba(0,163,255,0.4)',
              }} />
            </div>
          </div>

          {/* TOP SECTION: Band Room + Collaboration Timeline side by side */}
          <div className="grid-2" style={{ marginBottom: 'var(--spacing-lg)' }}>
            <BandRoomPanel />
            <CollaborationTimeline />
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 'var(--spacing-lg)', background: 'rgba(255,255,255,0.03)', padding: 4, borderRadius: 'var(--radius-md)', width: 'fit-content' }}>
            {(['band', 'overview', 'feed'] as const).map(tab => (
              <button key={tab} className={`btn ${activeTab === tab ? 'btn-primary' : 'btn-ghost'} btn-sm`}
                onClick={() => setActiveTab(tab)}>
                {tab === 'band' ? '📡 Band Detail' : tab === 'overview' ? '🤖 Agent Status' : '📡 Live Feed'}
              </button>
            ))}
          </div>

          {activeTab === 'band' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
              <BandArchitectureCard />
            </div>
          ) : activeTab === 'overview' ? (
            <div className="agent-grid">
              {currentAgents.length > 0
                ? currentAgents.map(agent => <AgentCard key={agent.name} agent={agent} />)
                : Object.entries(AGENT_META).map(([name]) => (
                    <AgentCard key={name} agent={{ name, status: 'idle', progress: 0, flags: [] }} />
                  ))
              }
            </div>
          ) : (
            <div className="card">
              <div className="card-header">
                <div className="card-title">📡 Real-time Agent Communication Log</div>
                <span className="badge badge-accent">{currentFeed.length} events</span>
              </div>
              <div className="activity-feed">
                {currentFeed.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 32, color: 'rgba(140,180,220,0.3)' }}>
                    Waiting for agent activity...
                  </div>
                ) : (
                  currentFeed.map((event, i) => (
                    <FeedEventRow key={i} event={event} />
                  ))
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** New: Band Architecture explainer card for judges */
function BandArchitectureCard() {
  return (
    <div className="card" style={{ borderColor: 'rgba(0,163,255,0.2)', background: 'rgba(0,163,255,0.03)' }}>
      <div className="card-title" style={{ marginBottom: 16, color: '#00a3ff' }}>
        📡 How Band Powers This Workflow
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
        {[
          { icon: '🏠', title: 'Band Room', desc: 'Dedicated coordination space created per incident. All agents share context here — not through direct API calls.' },
          { icon: '🔄', title: 'Context Bus', desc: 'Each agent publishes findings to the shared Band room. Commander synthesizes all outputs before generating a plan.' },
          { icon: '⚡', title: 'Parallel Execution', desc: 'Capacity, Staffing, and Resource agents run simultaneously — not sequentially. Band eliminates bottlenecks.' },
          { icon: '🛡️', title: 'Human Gate', desc: 'No action is taken without human approval. Band routes the final plan to the Operations Manager for sign-off.' },
        ].map(item => (
          <div key={item.title} style={{
            padding: 14, borderRadius: 10,
            background: 'rgba(0,0,0,0.15)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <div style={{ fontSize: '1.3rem', marginBottom: 8 }}>{item.icon}</div>
            <div style={{ fontWeight: 700, fontSize: '0.8rem', color: 'white', marginBottom: 6 }}>{item.title}</div>
            <div style={{ fontSize: '0.72rem', color: 'rgba(160,200,240,0.6)', lineHeight: 1.5 }}>{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function AgentCard({ agent }: { agent: AgentLiveState }) {
  const meta = AGENT_META[agent.name]
  if (!meta) return null

  return (
    <div className="agent-card" style={{
      borderColor: agent.status === 'active' || agent.status === 'thinking'
        ? `${meta.color}55` : 'var(--color-border)',
      boxShadow: agent.status === 'active' ? `0 0 20px ${meta.color}22` : 'none',
    }}>
      <div className="agent-card-header">
        <div className={`agent-icon ${meta.className}`} style={{ fontSize: '1.3rem' }}>{meta.icon}</div>
        <div style={{ flex: 1 }}>
          <div className="agent-name">{meta.fullName}</div>
          <div className="agent-role">{meta.role}</div>
        </div>
        <div className={`agent-status ${agent.status}`}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
          {agent.status === 'thinking' ? <span>Thinking<span className="thinking-dots" /></span> : agent.status}
        </div>
      </div>

      {/* Progress */}
      <div className="agent-progress-bar">
        <div className={`agent-progress-fill ${meta.className}`} style={{ width: `${agent.progress}%` }} />
      </div>

      {/* Current Step */}
      {agent.currentStep && agent.status !== 'completed' && (
        <div style={{ marginTop: 'var(--spacing-sm)', padding: '6px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: 'var(--radius-sm)', borderLeft: `2px solid ${meta.color}` }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: meta.color, marginBottom: 2 }}>
            [{agent.currentStep}]
          </div>
          <div style={{ fontSize: '0.75rem', color: 'rgba(180,220,255,0.7)' }}>{agent.stepContent}</div>
        </div>
      )}

      {/* Completed Summary */}
      {agent.status === 'completed' && agent.summary && (
        <div style={{ marginTop: 'var(--spacing-sm)' }}>
          <div style={{ fontSize: '0.75rem', color: 'rgba(180,220,255,0.7)', lineHeight: 1.5 }}>{agent.summary}</div>
          {agent.confidence !== undefined && (
            <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center' }}>
              <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.4)' }}>Confidence</div>
              <div style={{ height: 4, flex: 1, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${(agent.confidence || 0) * 100}%`, background: 'var(--color-success)', borderRadius: 2 }} />
              </div>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--color-success)' }}>{((agent.confidence || 0) * 100).toFixed(0)}%</div>
            </div>
          )}
          {agent.flags.length > 0 && (
            <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 3 }}>
              {agent.flags.slice(0, 2).map((flag, i) => (
                <div key={i} style={{ fontSize: '0.7rem', color: flag.includes('CRITICAL') ? 'var(--color-critical)' : 'var(--color-warning)', lineHeight: 1.4 }}>{flag}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FeedEventRow({ event }: { event: { event_type: string; agent_name?: string; step?: string; content?: string; output_summary?: string; message?: string; timestamp?: string } }) {
  const meta = event.agent_name ? AGENT_META[event.agent_name] : null
  const time = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString()

  const content =
    event.content || event.output_summary || event.message ||
    (event.event_type === 'plan:ready' ? 'Final action plan generated' : event.event_type)

  return (
    <div className="feed-event">
      <div className="feed-time">{time}</div>
      {meta && (
        <div className="feed-agent-tag" style={{ background: `${meta.color}20`, color: meta.color }}>
          {meta.icon} {event.agent_name?.replace('_agent', '').replace('_', ' ').toUpperCase()}
        </div>
      )}
      {event.step && (
        <div className="step-label">{event.step}</div>
      )}
      <div className="feed-content">{content}</div>
    </div>
  )
}
