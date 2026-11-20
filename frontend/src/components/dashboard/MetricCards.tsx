import { Activity, Boxes, Package, QrCode } from 'lucide-react'
import type { DashboardOverview } from '../../lib/api'

interface MetricCardsProps {
  overview: DashboardOverview | null
  loading: boolean
  onNavigate: (page: string) => void
}

export default function MetricCards({
  overview,
  loading,
  onNavigate,
}: MetricCardsProps) {
  const metrics = [
    {
      label: 'Total Products',
      page: 'Products',
      value: overview?.products.total,
      icon: Package,
      iconStyle: 'bg-blue-500/10 text-blue-400',
    },
    {
      label: 'Active QR Codes',
      page: 'QR Codes',
      value: overview?.qr_codes.active,
      icon: QrCode,
      iconStyle: 'bg-violet-500/10 text-violet-400',
    },
    {
      label: 'QR Batches',
      page: 'QR Batches',
      value: overview?.batches.total,
      icon: Boxes,
      iconStyle: 'bg-amber-500/10 text-amber-400',
    },
    {
      label: 'Total Scans',
      page: 'Scan Analytics',
      value: overview?.scans.total,
      icon: Activity,
      iconStyle: 'bg-emerald-500/10 text-emerald-400',
    },
  ]

  return (
    <div className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => {
        const Icon = metric.icon

        return (
          <button
            type="button"
            key={metric.label}
            onClick={() => onNavigate(metric.page)}
            aria-label={`Open ${metric.page}`}
            className="cursor-pointer rounded-xl border border-white/[0.07] bg-[#101827] p-5 text-left transition hover:border-white/[0.2] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-medium text-slate-400">
                {metric.label}
              </span>
              <div
                className={`flex h-9 w-9 items-center justify-center rounded-lg ${metric.iconStyle}`}
              >
                <Icon size={18} />
              </div>
            </div>

            <div className="mt-4">
              <span className="text-[27px] font-semibold tracking-tight text-white">
                {loading ? '...' : metric.value?.toLocaleString() ?? '—'}
              </span>
            </div>

            <p className="mt-1 text-[11px] text-slate-500">
              Live platform data
            </p>
          </button>
        )
      })}
    </div>
  )
}
