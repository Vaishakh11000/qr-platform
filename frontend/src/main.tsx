
import { StrictMode, useEffect, useState, type FormEvent } from 'react'
import { createRoot } from 'react-dom/client'
import { LockKeyhole, Mail, QrCode, ShieldCheck } from 'lucide-react'
import './index.css'
import App from './App'
import {
  getCurrentAdmin,
  hasSession,
  login,
  logout,
  type AdminIdentity,
} from './lib/api'

function AuthGate() {
  const [admin, setAdmin] = useState<AdminIdentity | null>(null)
  const [checking, setChecking] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let active = true

    async function restoreSession() {
      if (!hasSession()) {
        if (active) setChecking(false)
        return
      }

      try {
        const identity = await getCurrentAdmin()
        if (active) setAdmin(identity)
      } catch {
        logout()
      } finally {
        if (active) setChecking(false)
      }
    }

    void restoreSession()

    return () => {
      active = false
    }
  }, [])

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)

    try {
      await login(email.trim(), password)
      const identity = await getCurrentAdmin()
      setAdmin(identity)
      setPassword('')
    } catch (err) {
      logout()
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to sign in. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  function handleLogout() {
    logout()
    setAdmin(null)
    setPassword('')
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#090e1a]">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <QrCode size={30} className="animate-pulse text-blue-400" />
          <p className="text-sm">Checking your session...</p>
        </div>
      </div>
    )
  }

  if (admin) {
    return <App admin={admin} onLogout={handleLogout} />
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#090e1a] px-5 py-12 text-slate-100">
      <div className="pointer-events-none absolute -left-40 -top-40 h-96 w-96 rounded-full bg-blue-600/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-violet-600/10 blur-3xl" />

      <div className="relative grid w-full max-w-[950px] overflow-hidden rounded-2xl border border-white/[0.08] bg-[#101827] shadow-2xl shadow-black/30 md:grid-cols-2">
        <div className="hidden flex-col justify-between bg-gradient-to-br from-blue-600/20 via-[#111d33] to-[#101827] p-10 md:flex">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 text-white">
                <QrCode size={23} />
              </div>
              <div>
                <p className="text-sm font-semibold">QR Platform</p>
                <p className="text-[10px] tracking-[0.18em] text-slate-500">
                  ADMIN CONSOLE
                </p>
              </div>
            </div>

            <div className="mt-24">
              <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-blue-400/20 bg-blue-400/10 text-blue-300">
                <ShieldCheck size={29} />
              </div>
              <h1 className="max-w-xs text-3xl font-semibold leading-tight tracking-tight">
                Manage your products and QR ecosystem.
              </h1>
              <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">
                Your central workspace for product information, QR allocation,
                regions and scan analytics.
              </p>
            </div>
          </div>

          <p className="text-[11px] text-slate-600">
            Secure administrator access
          </p>
        </div>

        <div className="flex flex-col justify-center p-7 sm:p-10">
          <div className="mb-9 md:hidden">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 text-white">
                <QrCode size={22} />
              </div>
              <div>
                <p className="text-sm font-semibold">QR Platform</p>
                <p className="text-[10px] tracking-[0.18em] text-slate-500">
                  ADMIN CONSOLE
                </p>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium tracking-wider text-blue-400">
              ADMINISTRATOR ACCESS
            </p>
            <h2 className="mt-3 text-2xl font-semibold text-white">
              Welcome back
            </h2>
            <p className="mt-2 text-sm text-slate-400">
              Sign in to access your administration dashboard.
            </p>
          </div>

          <form onSubmit={handleLogin} className="mt-8 space-y-5">
            <div>
              <label
                htmlFor="admin-email"
                className="mb-2 block text-xs font-medium text-slate-300"
              >
                Email address
              </label>
              <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-[#090e1a] px-3.5 focus-within:border-blue-500/70">
                <Mail size={17} className="shrink-0 text-slate-500" />
                <input
                  id="admin-email"
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="admin@example.com"
                  className="h-12 w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="admin-password"
                className="mb-2 block text-xs font-medium text-slate-300"
              >
                Password
              </label>
              <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-[#090e1a] px-3.5 focus-within:border-blue-500/70">
                <LockKeyhole size={17} className="shrink-0 text-slate-500" />
                <input
                  id="admin-password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  className="h-12 w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
                />
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-3.5 py-3 text-xs text-rose-300"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="flex h-12 w-full items-center justify-center rounded-lg bg-blue-500 text-sm font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? 'Signing in...' : 'Sign in to dashboard'}
            </button>
          </form>

          <p className="mt-8 text-center text-[11px] text-slate-600">
            Authorized administrators only
          </p>
        </div>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthGate />
  </StrictMode>,
)
