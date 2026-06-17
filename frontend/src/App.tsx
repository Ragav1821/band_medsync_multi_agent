import { useState, useCallback } from 'react'
import { Navbar } from './components/shared/Navbar'
import { Sidebar } from './components/shared/Sidebar'
import { Dashboard } from './pages/Dashboard'
import { IncidentMonitor } from './pages/IncidentMonitor'
import { AgentActivity } from './pages/AgentActivity'
import { ActionPlanPage } from './pages/ActionPlan'
import { Simulation } from './pages/Simulation'
import { AuditTrail } from './pages/AuditTrail'
import { useStore } from './store/appStore'

function ToastContainer() {
  const { toasts, removeToast } = useStore()
  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast ${toast.type}`} onClick={() => removeToast(toast.id)} style={{ cursor: 'pointer' }}>
          <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'white', marginBottom: 3 }}>{toast.title}</div>
          <div style={{ fontSize: '0.78rem', color: 'rgba(180,220,255,0.7)', lineHeight: 1.4 }}>{toast.message}</div>
          <div style={{ fontSize: '0.65rem', color: 'rgba(140,180,220,0.3)', marginTop: 4 }}>Click to dismiss</div>
        </div>
      ))}
    </div>
  )
}

type Page = 'dashboard' | 'incidents' | 'agents' | 'action-plan' | 'simulation' | 'audit'

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard')
  const { incidents, selectIncident } = useStore()

  const activeIncidentCount = incidents.filter(i => i.status !== 'resolved').length

  const handleNavigate = useCallback((page: string, incidentId?: string) => {
    if (incidentId) selectIncident(incidentId)
    setCurrentPage(page as Page)
  }, [selectIncident])

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard': return <Dashboard onNavigate={handleNavigate} />
      case 'incidents': return <IncidentMonitor onNavigate={handleNavigate} />
      case 'agents': return <AgentActivity onNavigate={handleNavigate} />
      case 'action-plan': return <ActionPlanPage onNavigate={handleNavigate} />
      case 'simulation': return <Simulation onNavigate={handleNavigate} />
      case 'audit': return <AuditTrail />
      default: return <Dashboard onNavigate={handleNavigate} />
    }
  }

  return (
    <div className="app-layout">
      <Navbar />
      <Sidebar currentPage={currentPage} onNavigate={(p) => setCurrentPage(p as Page)} activeIncidentCount={activeIncidentCount} />
      <main className="main-content">
        {renderPage()}
      </main>
      <ToastContainer />
    </div>
  )
}

export default App
