import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { AlertCircle, ChevronLeft, ChevronRight, Download, FileSearch, LoaderCircle, RefreshCw, X } from 'lucide-react'
import { getAdminUsers, getAuditLog, getAuditLogs } from '../../lib/api'
import type { AdminUser, AuditLog } from '../../lib/api'

const PAGE_SIZE = 50
const EXPORT_PAGE_SIZE = 100
const EMPTY_FILTERS = { action: '', entity_type: '', entity_id: '', admin_id: '', from_date: '', to_date: '' }

function utcDateBoundary(value: string, endOfDay = false) {
  if (!value) return undefined
  return `${value}T${endOfDay ? '23:59:59.999999' : '00:00:00.000000'}Z`
}

function formatAuditTime(value: string) {
  return `${new Date(value).toLocaleString(undefined, { timeZone: 'UTC' })} UTC`
}

function csvCell(value: unknown) {
  let text = value == null ? '' : typeof value === 'string' ? value : JSON.stringify(value)
  if (/^\s*[=+\-@]/.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

function AuditLogsPage({ initialAuditEventId, searchTargetNonce }: { initialAuditEventId?: string; searchTargetNonce: number }) {
  const [items, setItems] = useState<AuditLog[]>([])
  const [admins, setAdmins] = useState<Map<string, AdminUser>>(new Map())
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [draftFilters, setDraftFilters] = useState(EMPTY_FILTERS)
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [reloadNonce, setReloadNonce] = useState(0)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<AuditLog | null>(null)
  const requestSequence = useRef(0)

  useEffect(() => {
    let active = true
    void getAdminUsers().then((rows) => {
      if (active) setAdmins(new Map(rows.map((admin) => [admin.id, admin])))
    }).catch(() => {
      // Audit history remains available when a former administrator no longer has an account.
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!initialAuditEventId) return
    let active = true
    getAuditLog(initialAuditEventId)
      .then((event) => { if (active) setSelected(event) })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not open the searched audit event.')
      })
    return () => { active = false }
  }, [initialAuditEventId, searchTargetNonce])

  function adminLabel(id: string | null) {
    if (!id) return 'System'
    const admin = admins.get(id)
    return admin ? `${admin.name} · ${admin.email}` : id
  }

  const load = useCallback(async () => {
    const requestId = ++requestSequence.current
    setLoading(true)
    setError('')
    try {
      const page = await getAuditLogs({
        offset,
        limit: PAGE_SIZE,
        action: filters.action.trim() || undefined,
        entity_type: filters.entity_type.trim() || undefined,
        entity_id: filters.entity_id.trim() || undefined,
        admin_id: filters.admin_id.trim() || undefined,
        created_from: utcDateBoundary(filters.from_date),
        created_to: utcDateBoundary(filters.to_date, true),
      })
      if (requestId === requestSequence.current) {
        setItems(page.items)
        setTotal(page.total)
      }
    } catch (err) {
      if (requestId === requestSequence.current) setError(err instanceof Error ? err.message : 'Could not load audit logs.')
    } finally {
      if (requestId === requestSequence.current) setLoading(false)
    }
  }, [offset, filters])

  useEffect(() => { void load() }, [load, reloadNonce])

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFilters({ ...draftFilters })
    setOffset(0)
    setReloadNonce((value) => value + 1)
  }

  function clearFilters() {
    setDraftFilters(EMPTY_FILTERS)
    setFilters(EMPTY_FILTERS)
    setOffset(0)
    setReloadNonce((value) => value + 1)
  }

  async function exportFilteredAuditLogs() {
    setExporting(true)
    setError('')
    try {
      const commonFilters = {
        action: filters.action.trim() || undefined,
        entity_type: filters.entity_type.trim() || undefined,
        entity_id: filters.entity_id.trim() || undefined,
        admin_id: filters.admin_id.trim() || undefined,
        created_from: utcDateBoundary(filters.from_date),
        created_to: utcDateBoundary(filters.to_date, true),
      }
      const exported: AuditLog[] = []
      for (let exportOffset = 0; exportOffset < total; exportOffset += EXPORT_PAGE_SIZE) {
        const page = await getAuditLogs({ ...commonFilters, offset: exportOffset, limit: EXPORT_PAGE_SIZE })
        exported.push(...page.items)
        if (page.items.length < EXPORT_PAGE_SIZE) break
      }
      const rows: unknown[][] = [
        ['Event ID', 'Created at (UTC)', 'Administrator', 'Admin ID', 'Action', 'Entity type', 'Entity ID', 'Old values', 'New values', 'IP hash'],
        ...exported.map((item) => [
          item.id,
          item.created_at,
          adminLabel(item.admin_id),
          item.admin_id,
          item.action,
          item.entity_type,
          item.entity_id,
          item.old_values,
          item.new_values,
          item.ip_hash,
        ]),
      ]
      const csv = `\uFEFF${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `qr-platform-audit-logs-${new Date().toISOString().slice(0, 10)}.csv`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not export audit logs.')
    } finally {
      setExporting(false)
    }
  }

  return <div>
    <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-sm text-slate-400">Administrative history</p><h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Audit Logs</h2><p className="mt-1 text-sm text-slate-500">Review recorded changes and who made them.</p></div><div className="flex gap-2"><button onClick={() => void exportFilteredAuditLogs()} disabled={exporting || loading || total === 0} className="flex items-center gap-2 rounded-lg border border-white/10 bg-[#101827] px-3 py-2.5 text-xs text-slate-300 hover:text-white disabled:opacity-40"><Download size={14} />{exporting ? 'Exporting…' : 'Export filtered CSV'}</button><button onClick={() => void load()} aria-label="Refresh audit logs" className="w-fit rounded-lg border border-white/10 bg-[#101827] p-2.5 text-slate-400 hover:text-white"><RefreshCw size={14} /></button></div></div>
    <form onSubmit={applyFilters} className="mb-5 grid gap-3 rounded-xl border border-white/[0.07] bg-[#101827] p-4 sm:grid-cols-2 xl:grid-cols-4">
      <label className="text-[10px] text-slate-400">Action<input value={draftFilters.action} onChange={(event) => setDraftFilters({ ...draftFilters, action: event.target.value })} placeholder="e.g. PRODUCT_UPDATED" className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-white placeholder:text-slate-600" /></label>
      <label className="text-[10px] text-slate-400">Entity type<input value={draftFilters.entity_type} onChange={(event) => setDraftFilters({ ...draftFilters, entity_type: event.target.value })} placeholder="e.g. PRODUCT" className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-white placeholder:text-slate-600" /></label>
      <label className="text-[10px] text-slate-400">Entity ID<input value={draftFilters.entity_id} onChange={(event) => setDraftFilters({ ...draftFilters, entity_id: event.target.value })} className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-white" /></label>
      <label className="text-[10px] text-slate-400">Administrator<select value={draftFilters.admin_id} onChange={(event) => setDraftFilters({ ...draftFilters, admin_id: event.target.value })} className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-white"><option value="">All administrators</option>{Array.from(admins.values()).sort((a, b) => a.name.localeCompare(b.name)).map((admin) => <option key={admin.id} value={admin.id}>{admin.name} · {admin.email}{admin.is_active ? '' : ' (inactive)'}</option>)}</select></label>
      <label className="text-[10px] text-slate-400">From date (UTC)<input type="date" value={draftFilters.from_date} max={draftFilters.to_date || undefined} onChange={(event) => setDraftFilters({ ...draftFilters, from_date: event.target.value })} className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-white" /></label>
      <label className="text-[10px] text-slate-400">To date (UTC)<input type="date" value={draftFilters.to_date} min={draftFilters.from_date || undefined} onChange={(event) => setDraftFilters({ ...draftFilters, to_date: event.target.value })} className="mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-white" /></label>
      <div className="flex items-end gap-2 sm:col-span-2"><button className="rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white">Apply filters</button><button type="button" onClick={clearFilters} className="rounded-lg border border-white/10 px-4 py-2.5 text-xs text-slate-300">Clear</button></div>
    </form>
    {error && <p className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}
    <section className="overflow-hidden rounded-xl border border-white/[0.07] bg-[#101827]"><div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-4"><h3 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><FileSearch size={15} /> Audit events</h3><span className="text-[10px] text-slate-500">{total.toLocaleString()} total</span></div><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead className="border-b border-white/[0.07] text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-5 py-4">Action</th><th className="px-5 py-4">Entity</th><th className="px-5 py-4">Entity ID</th><th className="px-5 py-4">Administrator</th><th className="px-5 py-4">Date (UTC)</th><th className="px-5 py-4 text-right">Details</th></tr></thead><tbody className="divide-y divide-white/[0.05] text-slate-300">{loading ? <tr><td colSpan={6} className="px-5 py-12 text-center text-slate-500"><LoaderCircle size={18} className="mx-auto animate-spin" /></td></tr> : items.length === 0 ? <tr><td colSpan={6} className="px-5 py-12 text-center text-slate-500">No audit events match these filters.</td></tr> : items.map((item) => <tr key={item.id} className="hover:bg-white/[0.02]"><td className="px-5 py-4 font-medium text-white">{item.action}</td><td className="px-5 py-4">{item.entity_type}</td><td className="max-w-[220px] truncate px-5 py-4 font-mono text-[10px] text-slate-500">{item.entity_id ?? '—'}</td><td className="max-w-[240px] truncate px-5 py-4 text-slate-400" title={item.admin_id ?? 'System'}>{adminLabel(item.admin_id)}</td><td className="px-5 py-4 text-slate-400">{formatAuditTime(item.created_at)}</td><td className="px-5 py-4 text-right"><button onClick={() => setSelected(item)} className="rounded-md border border-white/10 px-3 py-2 text-[10px] text-slate-300 hover:text-white">View</button></td></tr>)}</tbody></table></div><div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3 text-[10px] text-slate-500"><span>{items.length ? `Showing ${offset + 1}–${offset + items.length} of ${total}` : 'No events on this page'}</span><div className="flex gap-2"><button disabled={offset === 0 || loading} onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))} className="rounded-md border border-white/10 p-1.5 disabled:opacity-30"><ChevronLeft size={14} /></button><button disabled={offset + PAGE_SIZE >= total || loading} onClick={() => setOffset((current) => current + PAGE_SIZE)} className="rounded-md border border-white/10 p-1.5 disabled:opacity-30"><ChevronRight size={14} /></button></div></div></section>
    {selected && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null) }}><section className="w-full max-w-2xl rounded-2xl border border-white/10 bg-[#101827] p-6"><div className="mb-5 flex items-center justify-between"><div><h3 className="text-lg font-semibold text-white">{selected.action}</h3><p className="mt-1 text-xs text-slate-500">{selected.entity_type} · {adminLabel(selected.admin_id)} · {formatAuditTime(selected.created_at)}</p></div><button onClick={() => setSelected(null)} aria-label="Close details" className="text-slate-500 hover:text-white"><X size={18} /></button></div><div className="grid gap-4 sm:grid-cols-2">{[['Old values', selected.old_values], ['New values', selected.new_values]].map(([label, values]) => <div key={label as string}><h4 className="mb-2 text-xs font-semibold text-slate-300">{label as string}</h4><pre className="max-h-72 overflow-auto rounded-lg border border-white/[0.06] bg-[#0b1220] p-3 text-[10px] leading-5 text-slate-400">{JSON.stringify(values, null, 2) ?? '—'}</pre></div>)}</div><p className="mt-4 text-[10px] text-slate-500">Event ID: {selected.id}{selected.admin_id ? ` · Admin ID: ${selected.admin_id}` : ''}{selected.ip_hash ? ` · IP hash: ${selected.ip_hash}` : ''}</p></section></div>}
  </div>
}

export default AuditLogsPage
