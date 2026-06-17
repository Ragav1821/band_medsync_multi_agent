import { useStore } from '../../store/appStore'

export function Navbar() {
  const { wsConnected, metrics } = useStore()

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <div className="brand-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <div className="brand-name">MedSync AI</div>
          <div className="brand-sub">Emergency Command Center</div>
        </div>
      </div>

      <div className="navbar-status">
        {metrics && metrics.active_incidents > 0 && (
          <div className="status-pill" style={{ background: 'rgba(255,59,92,0.15)', color: 'var(--color-critical)', border: '1px solid rgba(255,59,92,0.3)', animation: 'critical-pulse 2s infinite' }}>
            <div className="status-dot" />
            {metrics.active_incidents} Active Incident{metrics.active_incidents !== 1 ? 's' : ''}
          </div>
        )}
        <div className="status-pill operational">
          <div className="status-dot" />
          {wsConnected ? 'Connected' : 'Connecting...'}
        </div>
        <div style={{ fontSize: '0.78rem', color: 'rgba(140,180,220,0.5)', fontFamily: 'var(--font-mono)' }}>
          {new Date().toLocaleTimeString()}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 12px', background: 'rgba(255,255,255,0.04)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, var(--color-accent), #7c3aed)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: 'white' }}>A</div>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'white' }}>Alex Chen</div>
            <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.5)' }}>Ops Manager</div>
          </div>
        </div>
      </div>
    </nav>
  )
}
