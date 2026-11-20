import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import MetricCards from './components/dashboard/MetricCards'
const ScanActivityChart = lazy(() => import('./components/dashboard/ScanActivityChart'))
import LocationAnalyticsCard from './components/dashboard/LocationAnalyticsCard'
import RecentActivityCard from './components/dashboard/RecentActivityCard'
import PlatformHealthCard from './components/dashboard/PlatformHealthCard'
import ProductsPage from './components/products/ProductsPage'
import CategoriesPage from './components/products/CategoriesPage'
import RegionsPage from './components/regions/RegionsPage'
import QRBatchesPage from './components/qr/QRBatchesPage'
import QRCodesPage from './components/qr/QRCodesPage'
import LocationPoliciesPage from './components/policies/LocationPoliciesPage'
import ScanAnalyticsPage from './components/analytics/ScanAnalyticsPage'
import AuditLogsPage from './components/audit/AuditLogsPage'
import FormsPage from './components/forms/FormsPage'
import AdministrationPage from './components/administration/AdministrationPage'
import DocumentationPage from './components/DocumentationPage'
import { useDashboardData } from './hooks/useDashboardData'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bell,
  Boxes,
  Building2,
  CircleHelp,
  ClipboardList,
  Download,
  FileText,
  LayoutDashboard,
  MapPin,
  Menu,
  Package,
  QrCode,
  RefreshCw,
  Search,
  ShieldCheck,
  Settings,
  Tags,
  X,
} from 'lucide-react'
import { searchPlatform } from './lib/api'
import type {
  AdminIdentity,
  DashboardOverview,
  GlobalSearchResult,
  LocationAnalytics,
  RecentActivity,
  ScanTrend,
} from './lib/api'

function csvCell(value: unknown) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

function downloadDashboardReport(
  overview: DashboardOverview,
  trends: ScanTrend[],
  location: LocationAnalytics,
  activity: RecentActivity[],
) {
  const rows: unknown[][] = [
    ['Section', 'Metric', 'Value', 'Details'],
    ['Report', 'Generated at', new Date().toISOString(), 'Dashboard snapshot'],
  ]

  for (const [section, metrics] of Object.entries(overview)) {
    for (const [metric, value] of Object.entries(metrics)) {
      rows.push([section, metric, value, 'Current total'])
    }
  }

  for (const day of trends) {
    rows.push(['Daily scans', day.date, day.total, `Allowed: ${day.allowed}; blocked: ${day.blocked}; pending: ${day.pending}; errors: ${day.error}`])
  }

  for (const [metric, value] of Object.entries(location.location_statuses)) {
    rows.push(['Location status', metric, value, 'All recorded scans'])
  }

  for (const [metric, value] of Object.entries(location.classifications)) {
    rows.push(['Region classification', metric, value, 'All recorded scans'])
  }

  for (const event of activity) {
    rows.push(['Recent activity', event.action, event.created_at, `${event.entity_type}${event.entity_id ? ` · ${event.entity_id}` : ''}`])
  }

  const csv = `\uFEFF${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `qr-platform-dashboard-${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const navigation = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Products', icon: Package },
  { label: 'Categories', icon: Tags },
  { label: 'QR Codes', icon: QrCode },
  { label: 'QR Batches', icon: Boxes },
  { label: 'Regions', icon: MapPin },
  { label: 'Location Policies', icon: ShieldCheck },
  { label: 'Forms', icon: FileText },
  { label: 'Scan Analytics', icon: Activity },
  { label: 'Audit Logs', icon: ClipboardList },
  { label: 'Administration', icon: Settings },
]

const dashboardDateLabel = new Date().toLocaleDateString(undefined, {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})


interface AppProps {
  admin: AdminIdentity
  onLogout: () => void
}

function App({ admin, onLogout }: AppProps) {
  const [activePage, setActivePage] = useState('Overview')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [searchResults, setSearchResults] = useState<GlobalSearchResult[]>([])
  const [searchTarget, setSearchTarget] = useState<GlobalSearchResult | null>(null)
  const [searchTargetNonce, setSearchTargetNonce] = useState(0)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [documentationOpen, setDocumentationOpen] = useState(false)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const {
    overview,
    scanTrends,
    locationAnalytics,
    recentActivity,
    loading: dashboardLoading,
    error: dashboardError,
    refresh: refreshDashboard,
  } = useDashboardData()

  useEffect(() => {
    const query = searchQuery.trim()
    if (query.length < 2) return
    let active = true
    const timer = window.setTimeout(() => {
      setSearchLoading(true)
      setSearchError('')
      void searchPlatform(query)
        .then((result) => { if (active) setSearchResults(result.items) })
        .catch((err: unknown) => { if (active) setSearchError(err instanceof Error ? err.message : 'Search could not be completed.') })
        .finally(() => { if (active) setSearchLoading(false) })
    }, 250)
    return () => { active = false; window.clearTimeout(timer) }
  }, [searchQuery])

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target
      if (target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))) return
      event.preventDefault()
      searchInputRef.current?.focus()
      setSearchOpen(true)
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  const notifications = overview ? [
    ...(overview.batches.failed > 0 ? [{ title: `${overview.batches.failed} QR batch${overview.batches.failed === 1 ? '' : 'es'} failed`, detail: 'Review generation status and regenerate if needed.', page: 'QR Batches' }] : []),
    ...(overview.scans.error > 0 ? [{ title: `${overview.scans.error} scan error${overview.scans.error === 1 ? '' : 's'} to review`, detail: 'Inspect recent scan errors and check for a repeated customer issue.', page: 'Scan Analytics' }] : []),
    ...(overview.batches.pending > 0 ? [{ title: `${overview.batches.pending} QR batch${overview.batches.pending === 1 ? '' : 'es'} pending`, detail: 'Check whether generation has completed.', page: 'QR Batches' }] : []),
    ...(Math.max(overview.qr_codes.active - overview.qr_codes.allocated, 0) > 0 ? [{ title: `${Math.max(overview.qr_codes.active - overview.qr_codes.allocated, 0)} active QR code${Math.max(overview.qr_codes.active - overview.qr_codes.allocated, 0) === 1 ? '' : 's'} unallocated`, detail: 'Allocate codes from their QR batch before customers scan them.', page: 'QR Batches' }] : []),
    ...(overview.products.draft > 0 ? [{ title: `${overview.products.draft} draft product${overview.products.draft === 1 ? '' : 's'} to review`, detail: 'Review product details and publish when they are ready for customers.', page: 'Products' }] : []),
  ] : []

  function openSearchResult(result: GlobalSearchResult) {
    setSearchTarget(result)
    setSearchTargetNonce((nonce) => nonce + 1)
    setActivePage(result.page)
    setSearchQuery('')
    setSearchResults([])
    setSearchError('')
    setSearchLoading(false)
    setSearchOpen(false)
  }
  return (
    <div className="min-h-screen bg-[#090e1a] text-slate-100">
      {sidebarOpen && (
        <button
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[250px] flex-col border-r border-white/[0.07] bg-[#0d1423] transition-transform duration-200 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-[76px] items-center justify-between border-b border-white/[0.07] px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-500 text-white shadow-lg shadow-blue-500/20">
              <QrCode size={21} />
            </div>
            <div>
              <p className="text-[15px] font-semibold tracking-wide">QR Platform</p>
              <p className="text-[10px] tracking-[0.18em] text-slate-500">ADMIN CONSOLE</p>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="text-slate-500 hover:text-white lg:hidden"
            aria-label="Close sidebar"
          >
            <X size={19} />
          </button>
        </div>

        <div className="px-4 pt-7">
          <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.18em] text-slate-500">
            WORKSPACE
          </p>
          <nav className="space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon
              const active = activePage === item.label

              return (
                <button
                  key={item.label}
                  onClick={() => {
                    setSearchTarget(null)
                    setActivePage(item.label)
                    setSidebarOpen(false)
                  }}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[13px] transition ${
                    active
                      ? 'bg-blue-500/10 font-medium text-blue-400'
                      : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-100'
                  }`}
                >
                  <Icon size={17} strokeWidth={1.8} />
                  <span>{item.label}</span>
                  {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-blue-400" />}
                </button>
              )
            })}
          </nav>
        </div>

        <div className="mt-auto p-4">
          <div className="mb-4 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-300">
              <CircleHelp size={15} className="text-slate-500" />
              Need assistance?
            </div>
            <p className="mb-3 text-[11px] leading-relaxed text-slate-500">
              Find workflows, setting locations, and integration requirements.
            </p>
            <button onClick={() => setDocumentationOpen(true)} className="text-xs font-medium text-blue-400 hover:text-blue-300">
              View documentation →
            </button>
          </div>
          <div className="flex items-center gap-3 border-t border-white/[0.07] pt-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-semibold">
              {admin.name.slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-slate-200">
                {admin.name}
              </p>
              <p className="text-[10px] text-slate-500">{admin.role}</p>
            </div>
            <button
              onClick={onLogout}
              title="Sign out"
              className="rounded-md px-2 py-1.5 text-[11px] text-slate-400 transition hover:bg-white/[0.06] hover:text-white"
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <div className="min-h-screen lg:pl-[250px]">
        <header className="sticky top-0 z-20 flex h-[76px] items-center justify-between border-b border-white/[0.07] bg-[#090e1a]/90 px-5 backdrop-blur-xl sm:px-8">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="text-slate-400 hover:text-white lg:hidden"
              aria-label="Open navigation"
            >
              <Menu size={21} />
            </button>
            <div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>Workspace</span>
                <span>/</span>
                <span className="text-slate-300">{activePage}</span>
              </div>
              <h1 className="mt-1 text-sm font-semibold text-white">{activePage}</h1>
            </div>
          </div>

          <div className="flex items-center gap-3 sm:gap-5">
            <div className="relative flex min-w-0 items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2">
              <Search size={15} className="text-slate-500" />
              <input
                ref={searchInputRef}
                value={searchQuery}
                onChange={(event) => { const value = event.target.value; setSearchQuery(value); setSearchOpen(true); if (value.trim().length < 2) { setSearchResults([]); setSearchLoading(false); setSearchError('') } }}
                onKeyDown={(event) => {
                  if (event.key !== 'Escape') return
                  event.preventDefault()
                  setSearchQuery('')
                  setSearchResults([])
                  setSearchError('')
                  setSearchLoading(false)
                  setSearchOpen(false)
                  searchInputRef.current?.blur()
                }}
                onFocus={() => setSearchOpen(true)}
                onBlur={() => window.setTimeout(() => setSearchOpen(false), 150)}
                placeholder="Search products, QR codes…"
                aria-label="Search platform records"
                className="w-32 min-w-0 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-500 sm:w-52"
              />
              <kbd className="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-slate-500">
                /
              </kbd>
              {searchOpen && <div className="absolute right-0 top-full z-50 mt-2 max-h-[70vh] w-[min(26rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-white/10 bg-[#101827] py-2 shadow-2xl">
                {searchQuery.trim().length < 2 ? <p className="px-4 py-3 text-xs text-slate-500">Type at least two characters to search products, categories, regions, QR codes and batches, policies, forms, and audit events.</p>
                  : searchLoading ? <p className="px-4 py-3 text-xs text-slate-400">Searching…</p>
                    : searchError ? <p role="alert" className="px-4 py-3 text-xs text-rose-300">{searchError}</p>
                      : searchResults.length === 0 ? <p className="px-4 py-3 text-xs text-slate-500">No matching records found.</p>
                        : searchResults.map((result) => <button key={`${result.kind}-${result.id}`} onMouseDown={(event) => event.preventDefault()} onClick={() => openSearchResult(result)} className="flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-white/[0.05]"><span className="mt-0.5 rounded bg-blue-500/10 px-1.5 py-1 text-[9px] font-semibold uppercase text-blue-300">{result.kind}</span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium text-slate-200">{result.title}</span><span className="mt-1 block truncate text-[10px] text-slate-500">{result.detail || result.page}</span></span><span className="mt-1 text-[9px] text-slate-600">{result.page}</span></button>)}
              </div>}
            </div>
            <button
              onClick={() => void refreshDashboard()}
              disabled={dashboardLoading}
              title="Refresh dashboard"
              aria-label="Refresh dashboard"
              className="text-slate-400 transition hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw
                size={17}
                className={dashboardLoading ? "animate-spin" : ""}
              />
            </button>
            <div className="relative">
              <button onClick={() => setNotificationsOpen((open) => !open)} className="relative text-slate-400 hover:text-white" aria-label="Notifications and action alerts" aria-expanded={notificationsOpen}>
                <Bell size={19} />
                {notifications.length > 0 && <span className="absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-400 px-1 text-[9px] font-bold text-slate-950">{notifications.length}</span>}
              </button>
              {notificationsOpen && <div className="absolute right-0 top-full z-50 mt-3 w-[min(23rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-white/10 bg-[#101827] shadow-2xl">
                <div className="flex items-center justify-between border-b border-white/[0.07] px-4 py-3"><div><h3 className="text-xs font-semibold text-white">Platform alerts</h3><p className="mt-1 text-[10px] text-slate-500">Live checks from platform records</p></div><span className="text-[10px] text-slate-500">{notifications.length} open</span></div>
                {dashboardLoading && !overview ? <p className="px-4 py-6 text-center text-xs text-slate-500">Loading platform status…</p>
                  : dashboardError && !overview ? <p role="alert" className="px-4 py-6 text-center text-xs text-rose-300">Alerts are unavailable because platform status could not be loaded. Use refresh to try again.</p>
                  : notifications.length === 0 ? <p className="px-4 py-6 text-center text-xs text-slate-500">No current action alerts.</p>
                    : <div className="divide-y divide-white/[0.05]">{notifications.map((item) => <button key={item.title} onClick={() => { setSearchTarget(null); setActivePage(item.page); setNotificationsOpen(false) }} className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-white/[0.04]"><AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-300" /><span className="min-w-0 flex-1"><span className="block text-xs font-medium text-slate-200">{item.title}</span><span className="mt-1 block text-[10px] leading-4 text-slate-500">{item.detail}</span></span><ArrowRight size={13} className="mt-1 text-slate-600" /></button>)}</div>}
              </div>}
            </div>
            <div className="hidden h-8 w-px bg-white/10 sm:block" />
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-500/20 text-[11px] font-semibold text-blue-300">
                {admin.name.slice(0, 2).toUpperCase()}
              </div>
              <div className="hidden sm:block">
                <p className="text-xs text-slate-200">{admin.name}</p>
                <p className="text-[10px] text-slate-500">{admin.role}</p>
              </div>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[1500px] p-5 sm:p-8">
          {activePage === 'Overview' ? (
            <>
              <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                  <p className="text-sm text-slate-400">{dashboardDateLabel}</p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-[27px]">
                    Dashboard overview
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Here's what's happening across your platform.
                  </p>
                </div>
                <button
                  onClick={() => {
                    if (overview && locationAnalytics) {
                      downloadDashboardReport(overview, scanTrends, locationAnalytics, recentActivity)
                    }
                  }}
                  disabled={!overview || !locationAnalytics}
                  title={!overview || !locationAnalytics ? 'Wait for dashboard data to load' : 'Download dashboard data as CSV'}
                  className="flex w-fit items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-xs font-medium text-slate-300 transition hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Download size={15} />
                  Export report
                </button>
              </div>

              {dashboardError && (
                <p className="mb-4 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300">
                  Dashboard data could not be loaded: {dashboardError}
                </p>
              )}
              <MetricCards overview={overview} loading={dashboardLoading} onNavigate={setActivePage} />


              <div className="mb-6 grid grid-cols-1 gap-5 xl:grid-cols-[1.7fr_1fr]">
                <Suspense
                  fallback={
                    <div className="min-h-[300px] animate-pulse rounded-xl border border-white/[0.07] bg-[#101827]" />
                  }
                >
                  <ScanActivityChart
                    data={scanTrends}
                    loading={dashboardLoading}
                  />
                </Suspense>

                <LocationAnalyticsCard data={locationAnalytics} loading={dashboardLoading} />
              </div>

              <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.4fr_1fr]">
                <RecentActivityCard
                  data={recentActivity}
                  loading={dashboardLoading}
                  onViewAll={() => { setSearchTarget(null); setActivePage('Audit Logs') }}
                />

                <PlatformHealthCard />
              </div>
            </>
          ) : activePage === 'Products' ? (
            <ProductsPage searchTargetId={searchTarget?.page === 'Products' && searchTarget.kind === 'Product' ? searchTarget.id : undefined} searchTargetNonce={searchTargetNonce} />
          ) : activePage === 'Categories' ? (
            <CategoriesPage searchTargetId={searchTarget?.page === 'Categories' && searchTarget.kind === 'Category' ? searchTarget.id : undefined} searchTargetNonce={searchTargetNonce} />
          ) : activePage === 'Regions' ? (
            <RegionsPage searchTargetId={searchTarget?.page === 'Regions' && searchTarget.kind === 'Region' ? searchTarget.id : undefined} searchTargetNonce={searchTargetNonce} />
          ) : activePage === 'QR Batches' ? (
            <QRBatchesPage searchTargetId={searchTarget?.page === 'QR Batches' && searchTarget.kind === 'QR batch' ? searchTarget.id : undefined} searchTargetNonce={searchTargetNonce} />
          ) : activePage === 'QR Codes' ? (
            <QRCodesPage searchTargetId={searchTarget?.page === 'QR Codes' && searchTarget.kind === 'QR code' ? searchTarget.id : undefined} searchTargetNonce={searchTargetNonce} />
          ) : activePage === 'Location Policies' ? (
            <LocationPoliciesPage searchTargetId={searchTarget?.page === 'Location Policies' && searchTarget.kind === 'Location policy' ? searchTarget.id : undefined} searchTargetNonce={searchTargetNonce} />
          ) : activePage === 'Forms' ? (
            <FormsPage searchTargetId={searchTarget?.page === 'Forms' && searchTarget.kind === 'Form' ? searchTarget.id : undefined} searchTargetNonce={searchTargetNonce} />
          ) : activePage === 'Scan Analytics' ? (
            <ScanAnalyticsPage />
          ) : activePage === 'Audit Logs' ? (
            <AuditLogsPage initialAuditEventId={searchTarget?.page === 'Audit Logs' && searchTarget.kind === 'Audit event' ? searchTarget.id : undefined} searchTargetNonce={searchTargetNonce} />
          ) : activePage === 'Administration' ? (
            <AdministrationPage admin={admin} onNavigate={(page) => { setSearchTarget(null); setActivePage(page) }} searchTargetKey={searchTarget?.page === 'Administration' ? searchTarget.target_key ?? undefined : undefined} searchTargetNonce={searchTargetNonce} />
          ) : (
            <section className="rounded-xl border border-white/[0.07] bg-[#101827] p-8 sm:p-12">
              <div className="mx-auto max-w-md text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-400">
                  {(() => {
                    const item = navigation.find((entry) => entry.label === activePage)
                    const Icon = item?.icon ?? Building2
                    return <Icon size={25} />
                  })()}
                </div>
                <h2 className="mt-5 text-lg font-semibold text-white">{activePage}</h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">
                  This section is part of the admin dashboard structure. Its interface and API integration will be built in the next stages.
                </p>
                <button
                  onClick={() => { setSearchTarget(null); setActivePage('Overview') }}
                  className="mt-6 rounded-lg bg-blue-500 px-4 py-2.5 text-xs font-medium text-white transition hover:bg-blue-400"
                >
                  Back to overview
                </button>
              </div>
            </section>
          )}

          <footer className="mt-8 flex flex-col justify-between gap-2 border-t border-white/[0.06] pt-5 text-[10px] text-slate-600 sm:flex-row">
            <span>QR Platform Admin Console</span>
            <span>Live dashboard data · System health monitoring</span>
          </footer>
        </main>
        <DocumentationPage
          open={documentationOpen}
          onClose={() => setDocumentationOpen(false)}
          onNavigate={(page) => { setSearchTarget(null); setActivePage(page) }}
        />
      </div>
    </div>
  )
}

export default App
