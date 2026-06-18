/**
 * LoginModal — MedSync AI (Phase 16 Security Hardening)
 *
 * Shown when a user tries to approve an action plan without being logged in.
 * Uses the JWT auth flow added in P0-2.
 *
 * Demo credentials are shown directly for hackathon evaluators.
 */
import { useState } from 'react'
import { useStore } from '../../store/appStore'

interface LoginModalProps {
  onClose: () => void
  onSuccess?: () => void
}

const DEMO_ACCOUNTS = [
  { username: 'ops.manager', role: 'Operations Manager', emoji: '🎯' },
  { username: 'compliance',  role: 'Compliance Officer',  emoji: '⚖️' },
  { username: 'cmo',         role: 'Chief Medical Officer', emoji: '👨‍⚕️' },
]

export function LoginModal({ onClose, onSuccess }: LoginModalProps) {
  const { login, authLoading } = useStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('MedSync@2026')
  const [error, setError]     = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(username, password)
      onSuccess?.()
      onClose()
    } catch (err: any) {
      setError(err.message || 'Login failed')
    }
  }

  const fillDemo = (u: string) => {
    setUsername(u)
    setPassword('MedSync@2026')
    setError('')
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,8,20,0.85)',
      backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: 'linear-gradient(135deg, rgba(10,25,47,0.98) 0%, rgba(17,38,67,0.98) 100%)',
        border: '1px solid rgba(0,229,160,0.25)',
        borderRadius: 16,
        padding: '2rem',
        width: '100%',
        maxWidth: 440,
        boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
          <div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff', marginBottom: 4 }}>
              🔐 Authentication Required
            </div>
            <div style={{ fontSize: '0.78rem', color: 'rgba(160,200,240,0.6)' }}>
              You must be authorised to approve action plans.
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'rgba(160,200,240,0.5)', cursor: 'pointer', fontSize: '1.2rem', padding: 4 }}
          >
            ✕
          </button>
        </div>

        {/* Quick-select demo accounts */}
        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'rgba(0,229,160,0.7)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem' }}>
            Demo Accounts
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {DEMO_ACCOUNTS.map(a => (
              <button
                key={a.username}
                onClick={() => fillDemo(a.username)}
                style={{
                  padding: '0.4rem 0.75rem',
                  borderRadius: 8,
                  border: username === a.username
                    ? '1px solid rgba(0,229,160,0.6)'
                    : '1px solid rgba(100,140,200,0.25)',
                  background: username === a.username
                    ? 'rgba(0,229,160,0.12)'
                    : 'rgba(255,255,255,0.04)',
                  color: username === a.username ? '#00e5a0' : 'rgba(160,200,240,0.8)',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                {a.emoji} {a.role}
              </button>
            ))}
          </div>
        </div>

        {/* Login form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'rgba(160,200,240,0.7)', marginBottom: 6 }}>
              Username
            </label>
            <input
              id="login-username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="e.g. ops.manager"
              required
              style={{
                width: '100%',
                padding: '0.6rem 0.75rem',
                borderRadius: 8,
                border: '1px solid rgba(100,140,200,0.3)',
                background: 'rgba(255,255,255,0.05)',
                color: '#fff',
                fontSize: '0.88rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'rgba(160,200,240,0.7)', marginBottom: 6 }}>
              Password
            </label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '0.6rem 0.75rem',
                borderRadius: 8,
                border: '1px solid rgba(100,140,200,0.3)',
                background: 'rgba(255,255,255,0.05)',
                color: '#fff',
                fontSize: '0.88rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {error && (
            <div style={{
              padding: '0.6rem 0.75rem',
              borderRadius: 8,
              background: 'rgba(255,60,60,0.12)',
              border: '1px solid rgba(255,60,60,0.3)',
              color: '#ff6b6b',
              fontSize: '0.78rem',
              marginBottom: '1rem',
            }}>
              ⚠️ {error}
            </div>
          )}

          <button
            id="login-submit-btn"
            type="submit"
            disabled={authLoading || !username}
            style={{
              width: '100%',
              padding: '0.7rem',
              borderRadius: 8,
              border: 'none',
              background: authLoading || !username
                ? 'rgba(0,229,160,0.3)'
                : 'linear-gradient(135deg, #00e5a0, #00b8d9)',
              color: '#000',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: authLoading || !username ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {authLoading ? '⏳ Signing in…' : '🔓 Sign In & Approve'}
          </button>
        </form>

        <div style={{ marginTop: '1rem', fontSize: '0.7rem', color: 'rgba(100,140,180,0.45)', textAlign: 'center' }}>
          Default password for all demo accounts: <code style={{ color: 'rgba(0,229,160,0.5)' }}>MedSync@2026</code>
        </div>
      </div>
    </div>
  )
}
