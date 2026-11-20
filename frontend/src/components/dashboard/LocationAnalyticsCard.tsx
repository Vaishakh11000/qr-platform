import { MapPin } from 'lucide-react'
import type { LocationAnalytics } from '../../lib/api'

interface LocationAnalyticsCardProps {
  data: LocationAnalytics | null
  loading: boolean
}

export default function LocationAnalyticsCard({
  data,
  loading,
}: LocationAnalyticsCardProps) {
  const statuses = data?.location_statuses ?? {}
  const classifications = data?.classifications ?? {}

  const locationItems = [
    {
      label: 'GPS verified',
      count: statuses.GPS ?? 0,
      color: 'bg-emerald-400',
    },
    {
      label: 'IP-derived',
      count: statuses.IP_DERIVED ?? 0,
      color: 'bg-blue-400',
    },
    {
      label: 'Skipped',
      count: statuses.SKIPPED ?? 0,
      color: 'bg-amber-400',
    },
    {
      label: 'Denied',
      count: statuses.DENIED ?? 0,
      color: 'bg-rose-400',
    },
    {
      label: 'Unavailable',
      count: statuses.UNAVAILABLE ?? 0,
      color: 'bg-orange-400',
    },
    {
      label: 'IP lookup failed',
      count: statuses.IP_LOOKUP_FAILED ?? 0,
      color: 'bg-purple-400',
    },
    {
      label: 'Uncertain',
      count: statuses.UNCERTAIN ?? 0,
      color: 'bg-slate-400',
    },
  ]

  const totalLocations = locationItems.reduce(
    (sum, item) => sum + item.count,
    0,
  )

  const classificationItems = [
    {
      label: 'Matched',
      count: classifications.MATCH ?? 0,
      color: 'text-emerald-400',
    },
    {
      label: 'Mismatch',
      count: classifications.MISMATCH ?? 0,
      color: 'text-amber-400',
    },
    {
      label: 'Unknown',
      count: classifications.UNKNOWN ?? 0,
      color: 'text-slate-300',
    },
  ]

  const totalClassifications = classificationItems.reduce(
    (sum, item) => sum + item.count,
    0,
  )

  return (
    <section className="rounded-xl border border-white/[0.07] bg-[#101827] p-5 sm:p-6">
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-white">
          Scan location status
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          How visitors are sharing their location
        </p>
      </div>

      {loading ? (
        <div className="py-12 text-center text-xs text-slate-500">
          Loading location analytics...
        </div>
      ) : (
        <>
          <div className="space-y-5">
            {locationItems.map((item) => {
              const percent =
                totalLocations > 0
                  ? (item.count / totalLocations) * 100
                  : 0

              return (
                <div key={item.label}>
                  <div className="mb-2 flex items-center justify-between text-xs">
                    <span className="text-slate-400">{item.label}</span>
                    <span className="font-medium text-slate-200">
                      {item.count.toLocaleString()}
                    </span>
                  </div>

                  <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
                    <div
                      className={`h-full rounded-full ${item.color}`}
                      style={{ width: `${percent}%` }}
                    />
                  </div>

                  <p className="mt-1.5 text-right text-[10px] text-slate-500">
                    {percent.toFixed(1)}%
                  </p>
                </div>
              )
            })}

            {totalLocations === 0 && (
              <p className="text-center text-xs text-slate-500">
                No location scan data available yet.
              </p>
            )}
          </div>

          <div className="mt-7 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3">
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <MapPin size={15} className="text-blue-400" />
              Region classification
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2">
              {classificationItems.map((item) => {
                const percent =
                  totalClassifications > 0
                    ? (item.count / totalClassifications) * 100
                    : 0

                return (
                  <div key={item.label}>
                    <p className={`text-lg font-semibold ${item.color}`}>
                      {percent.toFixed(1)}%
                    </p>
                    <p className="text-[10px] text-slate-500">
                      {item.label} ({item.count})
                    </p>
                  </div>
                )
              })}
            </div>

            {totalClassifications === 0 && (
              <p className="mt-3 text-[10px] text-slate-500">
                No region classifications available yet.
              </p>
            )}
          </div>
        </>
      )}
    </section>
  )
}
