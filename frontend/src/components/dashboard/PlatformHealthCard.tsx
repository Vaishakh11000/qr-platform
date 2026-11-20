import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, CheckCircle2, AlertCircle, LoaderCircle, RefreshCw } from 'lucide-react'
import {
  getApiHealth,
  getReadinessHealth,
} from '../../lib/api'
import type {
  ApiHealth,
  ReadinessHealth,
} from '../../lib/api'

type ServiceStatus = 'checking' | 'healthy' | 'unavailable'

export default function PlatformHealthCard() {
  const [apiStatus, setApiStatus] = useState<ServiceStatus>('checking')
  const [readinessStatus, setReadinessStatus] =
    useState<ServiceStatus>('checking')
  const [apiInfo, setApiInfo] = useState<ApiHealth | null>(null)
  const [readinessInfo, setReadinessInfo] =
    useState<ReadinessHealth | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const mountedRef = useRef(false)

  const checkHealth = useCallback(async () => {
    setRefreshing(true)
    setApiStatus('checking')
    setReadinessStatus('checking')
    try {
      const [apiResult, readinessResult] = await Promise.allSettled([
        getApiHealth(),
        getReadinessHealth(),
      ])
      if (!mountedRef.current) return

      if (apiResult.status === 'fulfilled') {
        setApiInfo(apiResult.value)
        setApiStatus(
          apiResult.value.status === 'healthy' ? 'healthy' : 'unavailable',
        )
      } else {
        setApiInfo(null)
        setApiStatus('unavailable')
      }

      if (readinessResult.status === 'fulfilled') {
        setReadinessInfo(readinessResult.value)
        setReadinessStatus(
          readinessResult.value.status === 'ready'
            ? 'healthy'
            : 'unavailable',
        )
      } else {
        setReadinessInfo(null)
        setReadinessStatus('unavailable')
      }
    } finally {
      if (mountedRef.current) setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    void checkHealth()
    return () => { mountedRef.current = false }
  }, [checkHealth])

  const databaseStatus = readinessStatus
  const postgisStatus = readinessStatus

  const services = [
    {
      label: 'API service',
      detail:
        apiStatus === 'healthy'
          ? apiInfo?.application ?? 'Operational'
          : apiStatus === 'checking'
            ? 'Checking...'
            : 'Unavailable',
      status: apiStatus,
    },
    {
      label: 'Database',
      detail:
        databaseStatus === 'healthy'
          ? readinessInfo?.database ?? 'Connected'
          : databaseStatus === 'checking'
            ? 'Checking...'
            : 'Unavailable',
      status: databaseStatus,
    },
    {
      label: 'PostGIS',
      detail:
        postgisStatus === 'healthy'
          ? `Version ${readinessInfo?.postgis ?? 'available'}`
          : postgisStatus === 'checking'
            ? 'Checking...'
            : 'Unavailable',
      status: postgisStatus,
    },
  ]

  const allHealthy = services.every(
    (service) => service.status === 'healthy',
  )
  const checking = services.some(
    (service) => service.status === 'checking',
  )

  return (
    <section className="rounded-xl border border-white/[0.07] bg-[#101827] p-5 sm:p-6">
      <div className="mb-5">
        <h3 className="text-sm font-semibold text-white">Platform health</h3>
        <div className="mt-1 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500">Live API and infrastructure checks</p>
          <button
            type="button"
            onClick={() => void checkHealth()}
            disabled={refreshing}
            aria-label="Refresh platform health"
            title="Refresh platform health"
            className="rounded p-1 text-slate-500 transition hover:bg-white/[0.05] hover:text-white disabled:cursor-wait disabled:opacity-50"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {services.map((service) => (
          <div
            key={service.label}
            className="flex items-center justify-between gap-3"
          >
            <div className="flex items-center gap-2.5">
              {service.status === 'checking' ? (
                <LoaderCircle size={16} className="animate-spin text-slate-400" />
              ) : service.status === 'healthy' ? (
                <CheckCircle2 size={16} className="text-emerald-400" />
              ) : (
                <AlertCircle size={16} className="text-red-400" />
              )}
              <span className="text-xs text-slate-300">{service.label}</span>
            </div>

            <span
              className={`text-[11px] ${
                service.status === 'healthy'
                  ? 'text-emerald-400'
                  : service.status === 'unavailable'
                    ? 'text-red-400'
                    : 'text-slate-400'
              }`}
            >
              {service.detail}
            </span>
          </div>
        ))}
      </div>

      <div
        className={`mt-6 rounded-lg border p-3 ${
          checking
            ? 'border-white/[0.07] bg-white/[0.03]'
            : allHealthy
              ? 'border-emerald-500/10 bg-emerald-500/[0.04]'
              : 'border-red-500/10 bg-red-500/[0.04]'
        }`}
      >
        <div
          className={`flex items-center gap-2 text-xs font-medium ${
            checking
              ? 'text-slate-300'
              : allHealthy
                ? 'text-emerald-400'
                : 'text-red-400'
          }`}
        >
          <Activity size={15} />
          {checking
            ? 'Checking system status'
            : allHealthy
              ? 'All monitored services operational'
              : 'One or more services unavailable'}
        </div>

        <p className="mt-1.5 text-[10px] leading-relaxed text-slate-500">
          Status is based on live backend health and readiness endpoints.
        </p>
      </div>
    </section>
  )
}
