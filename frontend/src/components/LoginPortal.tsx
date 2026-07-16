import { useState } from 'react'
import { useStore } from '../store'

type AuthMode = 'login' | 'register'

export default function LoginPortal() {
  const loginWithToken = useStore(state => state.loginWithToken)
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      if (mode === 'register') {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ org_name: orgName, admin_name: name, email, password })
        })
        const data = await res.json()
        if (!res.ok) {
          setError(data.detail || 'Registration failed')
          return
        }
        loginWithToken(data.token, data.employee, data.organization)
      } else {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        })
        const data = await res.json()
        if (!res.ok) {
          setError(data.detail || 'Login failed')
          return
        }
        loginWithToken(data.token, data.employee, data.organization)
      }
    } catch {
      setError('Network error. Is the server running?')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="h-screen w-full flex items-center justify-center bg-bg-main bg-magenta-gradient text-white">
      <div className="w-full max-w-sm bg-bg-panels border border-border-color rounded-2xl shadow-2xl p-8 flex flex-col gap-6">
        <div className="text-center">
          <h1 className="text-2xl font-semibold mb-1">Neelvak AIOS</h1>
          <p className="text-text-muted text-sm">
            {mode === 'login' ? 'Sign in to your workspace' : 'Register your organization'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {mode === 'register' && (
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-text-primary">Organization Name</label>
                <input 
                  type="text"
                  value={orgName}
                  onChange={e => setOrgName(e.target.value)}
                  className="w-full bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-orange smooth-transition"
                  placeholder="Acme Corp"
                  required
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-text-primary">Your Name</label>
                <input 
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  className="w-full bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-orange smooth-transition"
                  placeholder="John Doe"
                  required
                />
              </div>
            </>
          )}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-text-primary">Email address</label>
            <input 
              type="email" 
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-orange smooth-transition"
              placeholder="name@company.com"
              required
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-text-primary">Password</label>
            <input 
              type="password" 
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-bg-main border border-border-color rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent-orange smooth-transition"
              placeholder="••••••••"
              required
            />
          </div>

          {error && (
            <div className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button 
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 bg-white text-black font-medium py-2 rounded-lg hover:bg-slate-200 smooth-transition text-sm disabled:opacity-50"
          >
            {isLoading ? 'Processing...' : mode === 'login' ? 'Log in' : 'Create Organization'}
          </button>
        </form>

        <div className="text-center">
          <button 
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
            className="text-xs text-text-muted hover:text-white smooth-transition"
          >
            {mode === 'login' ? "Don't have an account? Register your organization" : 'Already have an account? Log in'}
          </button>
        </div>
      </div>
    </div>
  )
}
