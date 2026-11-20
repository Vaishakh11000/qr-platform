import { lazy, Suspense, useCallback, useEffect, useState, type FormEvent } from 'react'
import { AlertCircle, Download, RefreshCw, X } from 'lucide-react'
import { getAllProducts, getAllRegions, getScanAnalytics, regionDisplayLabel } from '../../lib/api'
import type { Product, Region, ScanAnalytics } from '../../lib/api'

const ScanActivityChart = lazy(() => import('../dashboard/ScanActivityChart'))

type Filters = {
  from_date: string
  to_date: string
  product_id: string
  qr_code_id: string
  region_id: string
  result_status: string
  location_status: string
}

function utcDate(daysAgo = 0) {
  return new Date(Date.now() - daysAgo * 86_400_000).toISOString().slice(0, 10)
}

const emptyAnalytics: ScanAnalytics = {
  from_date: '',
  to_date: '',
  summary: { total: 0, pending: 0, allowed: 0, blocked: 0, error: 0 },
  location_analytics: {
    location_statuses: {},
    classifications: {},
  },
  daily: [],
  products: [],
  regions: [],
  qr_codes: [],
}

const inputClass = 'mt-1.5 w-full rounded-lg border border-white/10 bg-[#0b1220] px-3 py-2.5 text-xs text-slate-200 outline-none focus:border-blue-500/50'
const cardClass = 'rounded-xl border border-white/[0.07] bg-[#101827] p-5'

function csvCell(value: unknown) {
  let text = String(value ?? '')
  if (/^\s*[=+\-@]/.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

function ScanAnalyticsPage() {
  const [draft, setDraft] = useState<Filters>({
    from_date: utcDate(29), to_date: utcDate(), product_id: '', qr_code_id: '',
    region_id: '', result_status: '', location_status: '',
  })
  const [filters, setFilters] = useState(draft)
  const [analytics, setAnalytics] = useState<ScanAnalytics>(emptyAnalytics)
  const [products, setProducts] = useState<Product[]>([])
  const [regions, setRegions] = useState<Region[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([getAllProducts(), getAllRegions()])
      .then(([productRows, regionRows]) => {
        if (!active) return
        setProducts(productRows)
        setRegions(regionRows)
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not load filter options.')
      })
    return () => { active = false }
  }, [])

  const fetchReport = useCallback(() => getScanAnalytics({
        from_date: filters.from_date,
        to_date: filters.to_date,
        product_id: filters.product_id || undefined,
        qr_code_id: filters.qr_code_id || undefined,
        region_id: filters.region_id || undefined,
        result_status: filters.result_status || undefined,
        location_status: filters.location_status || undefined,
      }), [filters])

  useEffect(() => {
    let active = true
    fetchReport()
      .then((result) => { if (active) setAnalytics(result) })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Could not load scan analytics.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [fetchReport])

  async function refresh() {
    setLoading(true)
    setError('')
    try {
      setAnalytics(await fetchReport())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load scan analytics.')
    } finally {
      setLoading(false)
    }
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setFilters({ ...draft })
  }

  function exportReport() {
    const selectedProduct = products.find((product) => product.id === filters.product_id)
    const selectedRegion = regions.find((region) => region.id === filters.region_id)
    const selectedQr = analytics.qr_codes.find((code) => code.qr_code_id === filters.qr_code_id)
    const rows: unknown[][] = [
      ['Section', 'Metric', 'Value', 'Details'],
      ['Report', 'From date (UTC)', analytics.from_date || filters.from_date, 'Applied filters'],
      ['Report', 'To date (UTC)', analytics.to_date || filters.to_date, 'Applied filters'],
      ['Report', 'Product filter', filters.product_id ? `${selectedProduct?.name ?? filters.product_id}${selectedProduct?.sku ? ` · ${selectedProduct.sku}` : ''}` : 'All products', 'Applied filters'],
      ['Report', 'QR code filter', filters.qr_code_id ? selectedQr ? `${selectedQr.batch_code} · …${selectedQr.token_suffix}` : filters.qr_code_id : 'All QR codes', 'Applied filters'],
      ['Report', 'Region filter', filters.region_id ? selectedRegion ? regionDisplayLabel(selectedRegion, regions) : filters.region_id : 'All regions', 'Applied filters'],
      ['Report', 'Scan outcome filter', filters.result_status || 'All outcomes', 'Applied filters'],
      ['Report', 'Location outcome filter', filters.location_status || 'All location outcomes', 'Applied filters'],
      ['Report', 'Breakdown coverage', 'Up to 100 rows per category', 'Summary totals and daily activity include all matching scan events.'],
      ['Summary', 'Total scans', summary.total, ''],
      ['Summary', 'Allowed', summary.allowed, ''],
      ['Summary', 'Blocked', summary.blocked, ''],
      ['Summary', 'Pending', summary.pending, ''],
      ['Summary', 'Errors', summary.error, ''],
    ]
    for (const day of analytics.daily) {
      rows.push(['Daily activity', day.date, day.total, `Allowed: ${day.allowed}; blocked: ${day.blocked}; pending: ${day.pending}; errors: ${day.error}`])
    }
    for (const [status, count] of Object.entries(analytics.location_analytics.location_statuses)) {
      rows.push(['Location outcome', status, count, ''])
    }
    for (const [classification, count] of Object.entries(analytics.location_analytics.classifications)) {
      rows.push(['Region check', classification, count, ''])
    }
    for (const item of analytics.products) rows.push(['Product activity', item.name, item.scans, item.sku ?? ''])
    for (const item of analytics.regions) rows.push(['Region activity', item.name, item.scans, item.region_code ?? ''])
    for (const item of analytics.qr_codes) rows.push(['QR activity', `${item.batch_code} · …${item.token_suffix}`, item.scans, item.qr_code_id])

    const csv = `\uFEFF${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `qr-scan-analytics-${filters.from_date}-to-${filters.to_date}.csv`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  function filterByQr(qrCodeId: string) {
    const next = { ...filters, qr_code_id: filters.qr_code_id === qrCodeId ? '' : qrCodeId }
    setLoading(true)
    setError('')
    setDraft((current) => ({ ...current, qr_code_id: next.qr_code_id }))
    setFilters(next)
  }

  const summary = analytics.summary
  const allowRate = summary.allowed + summary.blocked > 0
    ? (summary.allowed / (summary.allowed + summary.blocked)) * 100
    : 0
  const metricCards = [
    { label: 'Scans in range', value: summary.total, color: 'text-white' },
    { label: 'Allowed', value: summary.allowed, color: 'text-emerald-300' },
    { label: 'Blocked', value: summary.blocked, color: 'text-rose-300' },
    { label: 'Allow rate', value: `${allowRate.toFixed(1)}%`, color: 'text-blue-300' },
  ]

  return <div>
    <div className="mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
      <div><p className="text-sm text-slate-400">Stored customer scan events</p><h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Scan Analytics</h2><p className="mt-1 text-sm text-slate-500">Filter outcomes and compare activity by product, region and QR code.</p></div>
      <div className="flex flex-wrap gap-2">
        <button onClick={exportReport} disabled={loading} className="flex w-fit items-center gap-2 rounded-lg border border-white/10 bg-[#101827] px-3 py-2.5 text-xs text-slate-300 hover:text-white disabled:opacity-50"><Download size={14} />Export CSV</button>
        <button onClick={() => void refresh()} disabled={loading} aria-label="Refresh scan analytics" className="flex w-fit items-center gap-2 rounded-lg border border-white/10 bg-[#101827] px-3 py-2.5 text-xs text-slate-300 hover:text-white disabled:opacity-50"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} />Refresh</button>
      </div>
    </div>

    <form onSubmit={applyFilters} className={`${cardClass} mb-5`}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs text-slate-400">From date<input required type="date" value={draft.from_date} max={draft.to_date || undefined} onChange={(event) => setDraft({ ...draft, from_date: event.target.value })} className={inputClass} /></label>
        <label className="text-xs text-slate-400">To date<input required type="date" value={draft.to_date} min={draft.from_date || undefined} max={utcDate()} onChange={(event) => setDraft({ ...draft, to_date: event.target.value })} className={inputClass} /></label>
        <label className="text-xs text-slate-400">Product<select value={draft.product_id} onChange={(event) => setDraft({ ...draft, product_id: event.target.value })} className={inputClass}><option value="">All products</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} · {product.sku}</option>)}</select></label>
        <label className="text-xs text-slate-400">Region<select value={draft.region_id} onChange={(event) => setDraft({ ...draft, region_id: event.target.value })} className={inputClass}><option value="">All regions</option>{regions.map((region) => <option key={region.id} value={region.id}>{regionDisplayLabel(region, regions)}</option>)}</select></label>
        <label className="text-xs text-slate-400">Scan outcome<select value={draft.result_status} onChange={(event) => setDraft({ ...draft, result_status: event.target.value })} className={inputClass}><option value="">All outcomes</option><option value="ALLOWED">Allowed</option><option value="BLOCKED">Blocked</option><option value="PENDING">Pending</option><option value="ERROR">Error</option></select></label>
        <label className="text-xs text-slate-400">Location outcome<select value={draft.location_status} onChange={(event) => setDraft({ ...draft, location_status: event.target.value })} className={inputClass}><option value="">All location outcomes</option><option value="GPS">GPS</option><option value="IP_DERIVED">IP derived</option><option value="SKIPPED">Skipped</option><option value="DENIED">Denied</option><option value="UNAVAILABLE">Unavailable</option><option value="IP_LOOKUP_FAILED">IP lookup failed</option><option value="UNCERTAIN">Uncertain</option><option value="PENDING">Pending</option></select></label>
        {draft.qr_code_id && <div className="flex items-end"><button type="button" onClick={() => { const next = { ...draft, qr_code_id: '' }; setDraft(next); setFilters(next) }} className="flex items-center gap-1 rounded-lg border border-blue-500/30 px-3 py-2.5 text-xs text-blue-200"><X size={13} />Clear selected QR</button></div>}
        <div className="flex items-end"><button disabled={loading} className="w-full rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-50">Apply filters</button></div>
      </div>
    </form>

    {error && <p role="alert" className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle size={14} />{error}</p>}
    <p className="mb-3 text-xs text-slate-500">Showing {analytics.from_date || filters.from_date} through {analytics.to_date || filters.to_date} (UTC). Breakdown tables show up to 100 rows.</p>

    <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metricCards.map((item) => <section key={item.label} className={cardClass}><p className="text-xs text-slate-500">{item.label}</p><p className={`mt-2 text-2xl font-semibold ${item.color}`}>{loading ? '…' : typeof item.value === 'number' ? item.value.toLocaleString() : item.value}</p></section>)}</div>
    <div className="mb-5 grid gap-5 xl:grid-cols-[1.5fr_1fr]"><Suspense fallback={<div className="min-h-[360px] animate-pulse rounded-xl border border-white/[0.07] bg-[#101827]" />}><ScanActivityChart data={analytics.daily} loading={loading} days={analytics.daily.length} periodLabel={`${analytics.from_date} to ${analytics.to_date} · UTC`} /></Suspense><section className={cardClass}><h3 className="text-sm font-semibold text-white">Location outcomes</h3><p className="mt-1 text-xs text-slate-500">Counts for the selected filters.</p><div className="mt-4 grid grid-cols-2 gap-3">{Object.entries(analytics.location_analytics.location_statuses).map(([key, value]) => <div key={key} className="rounded-lg bg-white/[0.025] p-3"><p className="text-[10px] text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-1 text-lg font-semibold text-slate-200">{loading ? '…' : value.toLocaleString()}</p></div>)}</div><div className="mt-4 border-t border-white/[0.07] pt-3"><p className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">Region checks</p><div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-400">{Object.entries(analytics.location_analytics.classifications).map(([key, value]) => <span key={key}>{key.replaceAll('_', ' ')} <b className="ml-1 text-slate-200">{loading ? '…' : value}</b></span>)}</div></div></section></div>

    <div className="grid gap-5 xl:grid-cols-3">
      <Breakdown title="Product activity" headers={['Product', 'SKU', 'Scans']} rows={analytics.products.map((item) => [item.name, item.sku ?? '—', item.scans.toLocaleString()])} loading={loading} />
      <Breakdown title="Region activity" headers={['Region', 'Code', 'Scans']} rows={analytics.regions.map((item) => [item.name, item.region_code ?? '—', item.scans.toLocaleString()])} loading={loading} />
      <section className={cardClass}><h3 className="text-sm font-semibold text-white">QR activity</h3><p className="mt-1 text-xs text-slate-500">Select a code to filter the report to it.</p>{analytics.qr_codes.length === 0 ? <p className="mt-5 text-xs text-slate-500">No QR scans in this range.</p> : <div className="mt-4 space-y-2">{analytics.qr_codes.slice(0, 100).map((item) => <div key={item.qr_code_id} className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.025] px-3 py-2.5"><div className="min-w-0"><p className="truncate text-xs text-slate-200">{item.batch_code} · …{item.token_suffix}</p><p className="mt-0.5 text-[10px] text-slate-500">{item.scans.toLocaleString()} scans</p></div><button onClick={() => filterByQr(item.qr_code_id)} className="shrink-0 text-[10px] text-blue-300 hover:text-blue-200">{filters.qr_code_id === item.qr_code_id ? 'Selected' : 'Filter'}</button></div>)}</div>}</section>
    </div>
  </div>
}

function Breakdown({ title, headers, rows, loading }: { title: string; headers: string[]; rows: string[][]; loading: boolean }) {
  return <section className={cardClass}><h3 className="text-sm font-semibold text-white">{title}</h3>{rows.length === 0 ? <p className="mt-5 text-xs text-slate-500">{loading ? 'Loading…' : 'No scans in this range.'}</p> : <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-[10px] uppercase tracking-wider text-slate-500"><tr>{headers.map((header) => <th key={header} className="pb-2 pr-3">{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row[0]}-${index}`} className="border-t border-white/[0.06]">{row.map((value, cell) => <td key={cell} className={`py-2 pr-3 ${cell === 0 ? 'text-slate-200' : 'text-slate-400'}`}>{value}</td>)}</tr>)}</tbody></table></div>}</section>
}

export default ScanAnalyticsPage
