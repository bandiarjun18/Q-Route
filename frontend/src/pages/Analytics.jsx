import { useState, useEffect, useCallback } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { Button } from '../components/ui/Button.jsx'
import { AnalyticsSummaryCards } from '../components/analytics/AnalyticsSummaryCards.jsx'
import { ConvergenceChartCard } from '../components/analytics/ConvergenceChartCard.jsx'
import { OptimizationDetailsCard } from '../components/analytics/OptimizationDetailsCard.jsx'
import { RefreshIcon } from '../components/common/Icons.jsx'
import { getConvergenceHistory } from '../api/qroute.js'

export function Analytics() {
  const [analyticsData, setAnalyticsData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchAnalytics = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const data = await getConvergenceHistory()
      setAnalyticsData(data)
    } catch (err) {
      if (err?.message?.includes('409') || err?.message?.toLowerCase().includes('not run')) {
        setAnalyticsData({ n_iterations: 0, best_fitness: 0, stopped_early: false, history: [] })
      } else {
        setError(err?.message || 'Failed to retrieve convergence analytics from backend API.')
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const init = async () => {
      setIsLoading(true)
      try {
        const data = await getConvergenceHistory()
        if (mounted) setAnalyticsData(data)
      } catch (err) {
        if (mounted) {
          if (err?.message?.includes('409') || err?.message?.toLowerCase().includes('not run')) {
            setAnalyticsData({ n_iterations: 0, best_fitness: 0, stopped_early: false, history: [] })
          } else {
            setError(err?.message || 'Failed to retrieve convergence analytics from backend API.')
          }
        }
      } finally {
        if (mounted) setIsLoading(false)
      }
    }
    init()
    return () => {
      mounted = false
    }
  }, [])

  return (
    <div className="space-y-6 sm:space-y-8 w-full">
      {/* 1. Page Header with Refresh Action */}
      <PageHeader
        title="Analytics"
        subtitle="Analyze QPSO optimization performance and convergence behavior."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchAnalytics}
            isLoading={isLoading}
            leftIcon={<RefreshIcon className="w-3.5 h-3.5" />}
            className="text-xs h-8 px-3"
          >
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </Button>
        }
      />

      {/* Error Alert */}
      {error && (
        <div className="p-3.5 bg-rose-950/80 border border-rose-800/80 rounded-lg text-rose-300 text-xs sm:text-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="font-semibold">Unable to Load Analytics:</span>
            <span className="truncate">{error}</span>
          </div>
          <Button variant="danger" size="sm" onClick={fetchAnalytics} className="shrink-0 h-7 text-xs px-2.5">
            Retry
          </Button>
        </div>
      )}

      {/* 2. Analytics Summary Cards (4 Columns) */}
      <AnalyticsSummaryCards analyticsData={analyticsData} />

      {/* 3. Full-Width Convergence Line Chart */}
      <ConvergenceChartCard
        analyticsData={analyticsData}
        isLoading={isLoading}
      />

      {/* 4. Optimization Details & Algorithmic Telemetry */}
      <OptimizationDetailsCard analyticsData={analyticsData} />
    </div>
  )
}

export default Analytics
