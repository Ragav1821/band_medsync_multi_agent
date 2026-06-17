import { useState, useEffect } from 'react'
import { simulationApi, type SimulationScenario } from '../api/client'
import { useStore } from '../store/appStore'

const DEMO_SCENARIOS: SimulationScenario[] = [
  { id: 'sim_001', name: 'Mass Casualty Event — Critical', description: '50 trauma patients incoming from highway pile-up. ICU near capacity, severe nurse and ventilator shortage.', severity_label: 'LEVEL 3 — CRITICAL', tags: ['mass_casualty', 'critical'] },
  { id: 'sim_002', name: 'ED Overload — Major', description: 'Flu season surge pushing ED to breaking point. Staff adequate but capacity critical.', severity_label: 'LEVEL 2 — MAJOR', tags: ['ed_overload', 'major'] },
  { id: 'sim_003', name: 'ICU Saturation — Critical', description: 'ICU at 98% due to post-surgical complications. New critical patients incoming.', severity_label: 'LEVEL 3 — CRITICAL', tags: ['icu_saturation', 'critical'] },
  { id: 'sim_004', name: 'Staff Shortage Crisis — Critical', description: '40% nursing staff called out sick. Hospital at normal volume but dangerously understaffed.', severity_label: 'LEVEL 3 — CRITICAL', tags: ['staff_shortage', 'critical'] },
  { id: 'sim_005', name: 'Resource Shortage — Major', description: 'Supply chain disruption causing critical medication and equipment shortages.', severity_label: 'LEVEL 2 — MAJOR', tags: ['resource_shortage', 'major'] },
]

export function Simulation({ onNavigate }: { onNavigate: (page: string, id?: string) => void }) {
  const [scenarios, setScenarios] = useState<SimulationScenario[]>(DEMO_SCENARIOS)
  const [running, setRunning] = useState<string | null>(null)
  const { addIncident, selectIncident, addToast } = useStore()

  useEffect(() => {
    simulationApi.list()
      .then(res => setScenarios(res.data))
      .catch(() => setScenarios(DEMO_SCENARIOS))
  }, [])

  const runScenario = async (scenario: SimulationScenario) => {
    setRunning(scenario.id)
    try {
      const res = await simulationApi.run(scenario.id)
      const incident = res.data.incident
      addIncident(incident)
      selectIncident(incident.id)
      addToast({ type: 'info', title: `🧪 Simulation Started`, message: `"${scenario.name}" — agents activating...` })
      onNavigate('agents', incident.id)
    } catch {
      addToast({ type: 'warning', title: 'Backend Offline', message: 'Start the FastAPI backend to run live simulations. See README.' })
    } finally {
      setRunning(null)
    }
  }

  const severityClass = (label: string) => {
    if (label.includes('CRITICAL')) return 'badge-critical'
    if (label.includes('MAJOR')) return 'badge-warning'
    return 'badge-success'
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">🧪 Simulation Engine</h1>
        <p className="page-subtitle">Run pre-built emergency scenarios to test the multi-agent workflow</p>
      </div>

      {/* Info Banner */}
      <div style={{ background: 'rgba(0,163,255,0.06)', border: '1px solid rgba(0,163,255,0.2)', borderRadius: 'var(--radius-md)', padding: 'var(--spacing-md) var(--spacing-lg)', marginBottom: 'var(--spacing-xl)' }}>
        <div style={{ fontWeight: 700, color: 'var(--color-accent)', marginBottom: 4 }}>🎯 Hackathon Demo Mode</div>
        <div style={{ fontSize: '0.82rem', color: 'rgba(140,180,220,0.7)', lineHeight: 1.6 }}>
          Select any scenario to trigger the full 5-agent coordination workflow. Watch agents analyze in real-time,
          share context, resolve conflicts, and generate a compliant action plan — all without requiring real hospital data.
        </div>
      </div>

      {/* Scenarios Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 'var(--spacing-md)' }}>
        {scenarios.map(scenario => (
          <div key={scenario.id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontWeight: 700, color: 'white', fontSize: '0.95rem', marginBottom: 4 }}>{scenario.name}</div>
                <span className={`badge ${severityClass(scenario.severity_label)}`}>{scenario.severity_label}</span>
              </div>
            </div>
            <div style={{ fontSize: '0.82rem', color: 'rgba(160,200,240,0.65)', lineHeight: 1.6, flex: 1 }}>
              {scenario.description}
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {scenario.tags.map(tag => (
                <span key={tag} className="badge badge-info" style={{ fontSize: '0.62rem' }}>{tag}</span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, paddingTop: 'var(--spacing-sm)', borderTop: '1px solid var(--color-border)' }}>
              <div style={{ flex: 1, fontSize: '0.72rem', color: 'rgba(140,180,220,0.4)' }}>
                Triggers: 5 agents · WebSocket streaming · Compliance validation
              </div>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => runScenario(scenario)}
                disabled={running === scenario.id}
              >
                {running === scenario.id ? '⏳ Starting...' : '▶ Run Scenario'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Architecture Note */}
      <div className="card" style={{ marginTop: 'var(--spacing-xl)', borderColor: 'rgba(167,139,250,0.2)' }}>
        <div className="card-title" style={{ color: 'var(--color-info)', marginBottom: 'var(--spacing-md)' }}>🏗️ Simulation Architecture</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 'var(--spacing-sm)' }}>
          {[
            { step: '1', label: 'Scenario Load', detail: 'Pre-built parameters' },
            { step: '2', label: 'Agent Dispatch', detail: 'Parallel activation' },
            { step: '3', label: 'Analysis', detail: 'Context sharing' },
            { step: '4', label: 'Compliance', detail: 'Validation pass' },
            { step: '5', label: 'Action Plan', detail: 'Final synthesis' },
          ].map(item => (
            <div key={item.step} style={{ textAlign: 'center', padding: 'var(--spacing-md)', background: 'rgba(167,139,250,0.05)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(167,139,250,0.1)' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-info)', lineHeight: 1 }}>{item.step}</div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'white', marginTop: 4 }}>{item.label}</div>
              <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.4)', marginTop: 2 }}>{item.detail}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
