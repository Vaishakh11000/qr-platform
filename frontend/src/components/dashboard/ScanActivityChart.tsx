import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ScanTrend } from '../../lib/api'

interface ScanActivityChartProps {
  data: ScanTrend[]
  loading: boolean
  days?: number
  periodLabel?: string
}

export default function ScanActivityChart({
  data,
  loading,
  days = 7,
  periodLabel,
}: ScanActivityChartProps) {
  const totalScans = data.reduce((sum, item) => sum + item.total, 0)
  const allowedScans = data.reduce((sum, item) => sum + item.allowed, 0)
  const blockedScans = data.reduce((sum, item) => sum + item.blocked, 0)

  const chartData = data.map((item) => ({
    ...item,
    day: new Date(`${item.date}T00:00:00`).toLocaleDateString('en-IN',
      days <= 7 ? { weekday: 'short' } : { month: 'short', day: 'numeric' },
    ),
  }))

  return (
    <section className="rounded-xl border border-white/[0.07] bg-[#101827] p-5 sm:p-6">
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-white">Scan activity</h3>
        <p className="mt-1 text-xs text-slate-500">
          {periodLabel ?? `Scan volume over the last ${days} days`}
        </p>
      </div>

      <div className="mb-5 flex flex-wrap gap-6">
        <div>
          <p className="text-[11px] text-slate-500">Total scans</p>
          <p className="mt-1 text-xl font-semibold text-white">
            {loading ? '...' : totalScans.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-[11px] text-slate-500">Allowed</p>
          <p className="mt-1 text-xl font-semibold text-emerald-400">
            {loading ? '...' : allowedScans.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-[11px] text-slate-500">Blocked</p>
          <p className="mt-1 text-xl font-semibold text-rose-400">
            {loading ? '...' : blockedScans.toLocaleString()}
          </p>
        </div>
      </div>

      <div className="h-[245px] w-full">
        {loading ? (
          <div className="flex h-full items-center justify-center text-xs text-slate-500">
            Loading scan activity...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 5, left: -22, bottom: 0 }}>
              <defs>
                <linearGradient id="scanGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid stroke="#ffffff" strokeOpacity={0.06} vertical={false} />

              <XAxis
                dataKey="day"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#64748b', fontSize: 11 }}
                dy={10}
              />

              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#64748b', fontSize: 11 }}
              />

              <Tooltip
                contentStyle={{
                  background: '#182235',
                  border: '1px solid #334155',
                  borderRadius: 9,
                  color: '#e2e8f0',
                  fontSize: 12,
                }}
              />

              <Area
                type="monotone"
                dataKey="total"
                name="Total scans"
                stroke="#3b82f6"
                strokeWidth={2.5}
                fill="url(#scanGradient)"
              />

              <Area
                type="monotone"
                dataKey="allowed"
                name="Allowed"
                stroke="#34d399"
                strokeWidth={1.8}
                fill="transparent"
              />

              <Area
                type="monotone"
                dataKey="blocked"
                name="Blocked"
                stroke="#fb7185"
                strokeWidth={1.8}
                fill="transparent"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}
