interface SidebarProps {
  currentPage: string
  onNavigate: (page: string) => void
  activeIncidentCount: number
}

const navItems = [
  { id: 'dashboard', label: 'Command Center', icon: '⚡' },
  { id: 'incidents', label: 'Active Incidents', icon: '🚨' },
  { id: 'agents', label: 'Band Hub', icon: '📡' },
  { id: 'action-plan', label: 'Action Plans', icon: '📋' },
  { id: 'simulation', label: 'Simulation', icon: '🧪' },
  { id: 'audit', label: 'Audit Trail', icon: '📜' },
]

export function Sidebar({ currentPage, onNavigate, activeIncidentCount }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-section-label">Navigation</div>
      {navItems.map((item) => (
        <button
          key={item.id}
          className={`sidebar-item ${currentPage === item.id ? 'active' : ''}`}
          onClick={() => onNavigate(item.id)}
        >
          <span className="nav-icon" style={{ fontSize: '1rem', width: 20, textAlign: 'center' }}>{item.icon}</span>
          <span>{item.label}</span>
          {item.id === 'incidents' && activeIncidentCount > 0 && (
            <span className="sidebar-badge">{activeIncidentCount}</span>
          )}
          {item.id === 'agents' && activeIncidentCount > 0 && (
            <span className="sidebar-badge" style={{ background: '#00a3ff' }}>LIVE</span>
          )}
        </button>
      ))}

      <div className="sidebar-section-label" style={{ marginTop: 'auto' }}>System</div>
      <div style={{ padding: '12px var(--spacing-md)', borderRadius: 'var(--radius-md)', background: 'rgba(0,163,255,0.05)', border: '1px solid rgba(0,163,255,0.15)', marginBottom: 8 }}>
        <div style={{ fontSize: '0.7rem', color: '#00a3ff', fontWeight: 700, marginBottom: 4 }}>📡 BAND LAYER ACTIVE</div>
        <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.4)' }}>Coordination backbone ready</div>
      </div>
      <div style={{ padding: '12px var(--spacing-md)', borderRadius: 'var(--radius-md)', background: 'rgba(0,229,160,0.05)', border: '1px solid rgba(0,229,160,0.15)' }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--color-success)', fontWeight: 700, marginBottom: 4 }}>✅ ALL AGENTS READY</div>
        <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.4)' }}>5 agents operational</div>
      </div>
    </aside>
  )
}
