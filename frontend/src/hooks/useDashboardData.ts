import { useCallback, useEffect, useState } from 'react'
import {
  getDashboardOverview,
  getScanTrends,
  getLocationAnalytics,
  getRecentActivity,
} from '../lib/api'

import type {
  DashboardOverview,
  ScanTrend,
  LocationAnalytics,
  RecentActivity,
} from '../lib/api'

export function useDashboardData() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [scanTrends, setScanTrends] = useState<ScanTrend[]>([])
  const [locationAnalytics, setLocationAnalytics] =
    useState<LocationAnalytics | null>(null)
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const [overviewData, trendsData, locationData, activityData] =
        await Promise.all([
          getDashboardOverview(),
          getScanTrends(7),
          getLocationAnalytics(),
          getRecentActivity(10),
        ])

      setOverview(overviewData)
      setScanTrends(trendsData)
      setLocationAnalytics(locationData)
      setRecentActivity(activityData)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load dashboard',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return {
    overview,
    scanTrends,
    locationAnalytics,
    recentActivity,
    loading,
    error,
    refresh,
  }
}
