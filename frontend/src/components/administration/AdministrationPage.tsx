import { useEffect, useState, type FormEvent } from 'react'
import { createAdminUser, getAdminUsers, getPlatformSettings, setAdminUserActive, updatePlatformSettings, type AdminIdentity, type AdminUser } from '../../lib/api'

const cardClass = 'rounded-xl border border-white/[0.07] bg-[#101827] p-5'
const inputClass = 'mt-2 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-sm text-white outline-none focus:border-blue-500/50'

function publicAddressCheck(value: string) {
  if (!value.trim()) {
    return {
      label: 'Needs address',
      detail: 'Set the customer-facing website address before generating QR codes.',
      className: 'text-amber-300',
    }
  }

  try {
    const url = new URL(value)
    const localHost = ['localhost', '127.0.0.1', '::1'].includes(url.hostname)

    if (localHost) {
      return {
        label: 'Local address',
        detail: 'Phones treat localhost as the phone itself. Use a reachable website address for customer QR codes.',
        className: 'text-amber-300',
      }
    }

    if (url.protocol !== 'https:') {
      return {
        label: 'HTTPS required',
        detail: 'Phone location permission requires HTTPS. Configure HTTPS before distributing QR codes.',
        className: 'text-amber-300',
      }
    }

    return {
      label: 'HTTPS address set',
      detail: 'The address uses HTTPS. Confirm its DNS, certificate, and phone access before printing QR codes.',
      className: 'text-emerald-300',
    }
  } catch {
    return {
      label: 'Check address',
      detail: 'Enter a valid website URL, then verify it from a customer phone.',
      className: 'text-amber-300',
    }
  }
}

export default function AdministrationPage({ admin, onNavigate, searchTargetKey, searchTargetNonce }: { admin: AdminIdentity; onNavigate: (page: string) => void; searchTargetKey?: string; searchTargetNonce: number }) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [publicBaseUrl, setPublicBaseUrl] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [highlightedSetting, setHighlightedSetting] = useState('')
  const addressCheck = publicAddressCheck(publicBaseUrl)

  useEffect(() => {
    if (!searchTargetKey) return
    const target = document.getElementById(searchTargetKey)
    if (!target) return
    setHighlightedSetting(searchTargetKey)
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const timeout = window.setTimeout(() => setHighlightedSetting(''), 2400)
    return () => window.clearTimeout(timeout)
  }, [searchTargetKey, searchTargetNonce])

  const targetClass = (key: string) => highlightedSetting === key ? ' ring-2 ring-blue-400/70' : ''

  useEffect(() => {
    let active = true
    Promise.all([getAdminUsers(), getPlatformSettings()])
      .then(([userRows, settings]) => {
        if (!active) return
        setUsers(userRows)
        setPublicBaseUrl(settings.public_base_url)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not load administration data.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      const saved = await updatePlatformSettings({ public_base_url: publicBaseUrl.trim() })
      setPublicBaseUrl(saved.public_base_url)
      setNotice('Public QR address saved. New QR links and exports will use this address.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save settings.')
    } finally { setBusy(false) }
  }

  async function addAdmin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      const created = await createAdminUser({ name: name.trim(), email: email.trim(), password })
      setUsers((current) => [...current, created])
      setName(''); setEmail(''); setPassword('')
      setNotice(`Administrator ${created.email} created.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create administrator.')
    } finally { setBusy(false) }
  }

  async function toggleAdmin(user: AdminUser) {
    setBusy(true); setError(''); setNotice('')
    try {
      const updated = await setAdminUserActive(user.id, !user.is_active)
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update administrator.')
    } finally { setBusy(false) }
  }

  return <div className="space-y-6">
    <div>
      <h2 className="text-xl font-semibold text-white">Administration and settings</h2>
      <p className="mt-1 text-sm text-slate-400">Manage administrator access, platform settings, and integration status.</p>
    </div>
    {error && <p role="alert" className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-300">{error}</p>}
    {notice && <p role="status" className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-300">{notice}</p>}

    <section className={cardClass}>
      <div className="mb-4"><h3 className="text-base font-semibold text-white">Integrations and service setup</h3><p className="mt-1 text-xs text-slate-400">Open the relevant settings for supported features. Services that need provider credentials or code work are marked as not connected.</p></div>
      <div className="grid gap-3 lg:grid-cols-2">
        <div id="integration-public-qr" className={`rounded-lg border border-white/[0.07] bg-white/[0.02] p-4${targetClass('integration-public-qr')}`}><div className="flex items-center justify-between gap-3"><h4 className="text-sm font-medium text-slate-200">Public QR website</h4><span className={`text-[10px] ${loading ? 'text-slate-400' : addressCheck.className}`}>{loading ? 'Checking address…' : addressCheck.label}</span></div><p className="mt-2 text-xs leading-5 text-slate-500">{loading ? 'Loading the configured customer-facing address.' : addressCheck.detail}</p><button onClick={() => document.getElementById('public-qr-address')?.scrollIntoView({ behavior: 'smooth', block: 'center' })} className="mt-3 text-xs font-medium text-blue-300 hover:text-blue-200">Edit public address ↓</button></div>
        <div id="integration-gps" className={`rounded-lg border border-white/[0.07] bg-white/[0.02] p-4${targetClass('integration-gps')}`}><div className="flex items-center justify-between gap-3"><h4 className="text-sm font-medium text-slate-200">GPS collection</h4><span className="text-[10px] text-emerald-300">Browser based</span></div><p className="mt-2 text-xs leading-5 text-slate-500">GPS uses the customer’s browser and device permission. Set whether it is required and where the policy applies.</p><button onClick={() => onNavigate('Location Policies')} className="mt-3 text-xs font-medium text-blue-300 hover:text-blue-200">Open location policies →</button></div>
        <div id="integration-ip-geolocation" className={`rounded-lg border border-amber-500/15 bg-amber-500/[0.03] p-4${targetClass('integration-ip-geolocation')}`}><div className="flex items-center justify-between gap-3"><h4 className="text-sm font-medium text-slate-200">IP geolocation</h4><span className="text-[10px] text-amber-300">Not connected</span></div><p className="mt-2 text-xs leading-5 text-slate-500">GPS/IP fallback needs a geolocation provider, credentials, and backend integration. The current app does not return an IP-derived location.</p></div>
        <div id="integration-email-push" className={`rounded-lg border border-amber-500/15 bg-amber-500/[0.03] p-4${targetClass('integration-email-push')}`}><div className="flex items-center justify-between gap-3"><h4 className="text-sm font-medium text-slate-200">Email and push delivery</h4><span className="text-[10px] text-amber-300">Not connected</span></div><p className="mt-2 text-xs leading-5 text-slate-500">The bell shows live platform alerts. Sending email or push notifications requires a delivery provider and code integration.</p></div>
        <div id="integration-media-storage" className={`rounded-lg border border-white/[0.07] bg-white/[0.02] p-4 lg:col-span-2${targetClass('integration-media-storage')}`}><div className="flex items-center justify-between gap-3"><h4 className="text-sm font-medium text-slate-200">Product media storage</h4><span className="text-[10px] text-slate-300">Deployment configured</span></div><p className="mt-2 text-xs leading-5 text-slate-500">Production media uses a persistent volume. Set its root and backup routine in deployment configuration.</p></div>
      </div>
    </section>

    <section id="public-qr-address" className={`${cardClass}${targetClass('public-qr-address')}`}>
      <h3 className="text-base font-semibold text-white">Public QR address</h3>
      <p className="mt-1 text-xs text-slate-400">Use the website address that customers’ phones can reach. Changing it affects new QR exports and displayed scan links; already printed QR images need to be regenerated.</p>
      <form onSubmit={(event) => void saveSettings(event)} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex-1 text-xs text-slate-300">Base URL<input required type="url" value={publicBaseUrl} onChange={(event) => setPublicBaseUrl(event.target.value)} placeholder="https://products.example.com" className={inputClass} /></label>
        <button disabled={busy || loading} className="rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">Save address</button>
      </form>
    </section>

    <section id="administrators" className={`${cardClass}${targetClass('administrators')}`}>
      <h3 className="text-base font-semibold text-white">Administrators</h3>
      <p className="mt-1 text-xs text-slate-400">Accounts created here receive the current SUPER_ADMIN access level.</p>
      <form onSubmit={(event) => void addAdmin(event)} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs text-slate-300">Name<input required maxLength={150} value={name} onChange={(event) => setName(event.target.value)} className={inputClass} /></label>
        <label className="text-xs text-slate-300">Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className={inputClass} /></label>
        <label className="text-xs text-slate-300">Temporary password<input required type="password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} className={inputClass} /></label>
        <button disabled={busy || loading} className="self-end rounded-lg border border-white/10 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/[0.05] disabled:opacity-50">Add administrator</button>
      </form>

      {loading ? <p className="mt-5 text-sm text-slate-400">Loading administrators…</p> : users.length === 0 ? <p className="mt-5 text-sm text-slate-400">No administrator accounts found.</p> : (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[650px] text-left text-sm">
            <thead className="text-xs text-slate-500"><tr><th className="py-2">Name</th><th>Email</th><th>Last sign in</th><th>Status</th><th /></tr></thead>
            <tbody>{users.map((user) => <tr key={user.id} className="border-t border-white/[0.06]">
              <td className="py-3 text-slate-200">{user.name}{user.id === admin.id && <span className="ml-2 text-xs text-slate-500">You</span>}</td>
              <td className="text-slate-400">{user.email}</td>
              <td className="text-slate-400">{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}</td>
              <td><span className={user.is_active ? 'text-emerald-300' : 'text-slate-500'}>{user.is_active ? 'Active' : 'Inactive'}</span></td>
              <td className="text-right">{user.id !== admin.id && <button disabled={busy} onClick={() => void toggleAdmin(user)} className="text-xs text-blue-300 hover:text-blue-200 disabled:opacity-50">{user.is_active ? 'Deactivate' : 'Reactivate'}</button>}</td>
            </tr>)}</tbody>
          </table>
        </div>
      )}
    </section>
  </div>
}
