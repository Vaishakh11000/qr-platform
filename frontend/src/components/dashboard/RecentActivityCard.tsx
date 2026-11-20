import {
  Activity,
  ClipboardList,
  MapPin,
  Package,
  QrCode,
  ShieldCheck,
} from 'lucide-react'
import type { RecentActivity } from '../../lib/api'

interface RecentActivityCardProps {
  data: RecentActivity[]
  loading: boolean
  onViewAll: () => void
}

function getActivityDetails(activity: RecentActivity) {
  const action = activity.action.toLowerCase()

  if (action.includes('qr') || action.includes('batch')) {
    return {
      icon: QrCode,
      color: 'text-violet-400',
      bg: 'bg-violet-400/10',
    }
  }

  if (action.includes('product')) {
    return {
      icon: Package,
      color: 'text-blue-400',
      bg: 'bg-blue-400/10',
    }
  }

  if (action.includes('region')) {
    return {
      icon: MapPin,
      color: 'text-amber-400',
      bg: 'bg-amber-400/10',
    }
  }

  if (action.includes('location_policy')) {
    return {
      icon: ShieldCheck,
      color: 'text-emerald-400',
      bg: 'bg-emerald-400/10',
    }
  }

  return {
    icon: Activity,
    color: 'text-slate-400',
    bg: 'bg-slate-400/10',
  }
}

function formatAction(action: string) {
  return action
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function formatDate(value: string) {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Invalid date'
  }

  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function RecentActivityCard({
  data,
  loading,
  onViewAll,
}: RecentActivityCardProps) {
  return (
    <section className="rounded-xl border border-white/[0.07] bg-[#101827] p-5 sm:p-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">Recent activity</h3>
          <p className="mt-1 text-xs text-slate-500">
            Latest administrative actions
          </p>
        </div>

        <button
          onClick={onViewAll}
          className="text-xs font-medium text-blue-400 hover:text-blue-300"
        >
          View audit logs →
        </button>
      </div>

      {loading ? (
        <div className="py-10 text-center text-xs text-slate-500">
          Loading recent activity...
        </div>
      ) : data.length === 0 ? (
        <div className="py-10 text-center">
          <ClipboardList
            size={24}
            className="mx-auto mb-3 text-slate-600"
          />
          <p className="text-xs text-slate-400">No recent activity yet</p>
          <p className="mt-1 text-[11px] text-slate-600">
            Administrative actions will appear here.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-white/[0.06]">
          {data.map((activity) => {
            const details = getActivityDetails(activity)
            const Icon = details.icon

            return (
              <div
                key={activity.id}
                className="flex items-center gap-3 py-4 first:pt-1 last:pb-1"
              >
                <div
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${details.bg} ${details.color}`}
                >
                  <Icon size={17} />
                </div>

                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-slate-200">
                    {formatAction(activity.action)}
                  </p>
                  <p className="mt-1 truncate text-[11px] text-slate-500">
                    {activity.entity_type}
                    {activity.entity_id
                      ? ` · ${activity.entity_id}`
                      : ''}
                  </p>
                </div>

                <span className="shrink-0 text-right text-[10px] text-slate-500">
                  {formatDate(activity.created_at)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
