import { useState, useEffect, useCallback } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { Button } from '../components/ui/Button.jsx'
import { RouteSummaryCards } from '../components/routes/RouteSummaryCards.jsx'
import { ActiveRoutesList } from '../components/routes/ActiveRoutesList.jsx'
import { RouteVisualizationCanvas } from '../components/routes/RouteVisualizationCanvas.jsx'
import { SelectedRouteDetails } from '../components/routes/SelectedRouteDetails.jsx'
import { RefreshIcon } from '../components/common/Icons.jsx'
import { getCurrentRoutes, getGeographicRoutes } from '../api/qroute.js'
import { networkPreviewData } from '../data/dashboardData.js'

export function LiveRoutes() {
  const [routesData, setRoutesData] = useState(null)
  const [geoData, setGeoData] = useState(null)
  const [selectedVehicleId, setSelectedVehicleId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchRoutes = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const [routesRes, geoRes] = await Promise.allSettled([
        getCurrentRoutes(),
        getGeographicRoutes(),
      ])

      if (routesRes.status === 'fulfilled') {
        const data = routesRes.value
        setRoutesData(data)
        if (data?.routes?.length > 0) {
          setSelectedVehicleId((prev) => {
            const exists = data.routes.some((r) => r.vehicle_id === prev)
            return exists ? prev : data.routes[0].vehicle_id
          })
        } else {
          setSelectedVehicleId(null)
        }
      } else {
        const err = routesRes.reason
        if (err?.message?.includes('409') || err?.message?.toLowerCase().includes('not configured')) {
          setRoutesData({ total_active: 0, routes: [] })
        } else {
          setError(err?.message || 'Failed to retrieve active routes from backend API.')
        }
      }

      if (geoRes.status === 'fulfilled') {
        setGeoData(geoRes.value)
      } else {
        setGeoData(null)
      }
    } catch (err) {
      setError(err?.message || 'Failed to retrieve active routes from backend API.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    let ignore = false
    const load = async () => {
      setIsLoading(true)
      try {
        const [routesRes, geoRes] = await Promise.allSettled([
          getCurrentRoutes(),
          getGeographicRoutes(),
        ])
        if (!ignore) {
          if (routesRes.status === 'fulfilled') {
            const data = routesRes.value
            setRoutesData(data)
            if (data?.routes?.length > 0) {
              setSelectedVehicleId(data.routes[0].vehicle_id)
            }
          } else {
            const err = routesRes.reason
            if (err?.message?.includes('409') || err?.message?.toLowerCase().includes('not configured')) {
              setRoutesData({ total_active: 0, routes: [] })
            } else {
              setError(err?.message || 'Failed to retrieve active routes from backend API.')
            }
          }
          if (geoRes.status === 'fulfilled') {
            setGeoData(geoRes.value)
          }
        }
      } catch (err) {
        if (!ignore) {
          setError(err?.message || 'Failed to retrieve active routes from backend API.')
        }
      } finally {
        if (!ignore) setIsLoading(false)
      }
    }
    load()
    return () => {
      ignore = true
    }
  }, [])



  const routes = routesData?.routes || []
  const selectedRoute = routes.find((r) => r.vehicle_id === selectedVehicleId)

  return (
    <div className="space-y-6 sm:space-y-8 w-full">
      {/* 1. Page Header with Refresh Action */}
      <PageHeader
        title="Live Routes"
        subtitle="Monitor active vehicle routes and current route conditions."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchRoutes}
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
            <span className="font-semibold">Unable to Load Routes:</span>
            <span className="truncate">{error}</span>
          </div>
          <Button variant="danger" size="sm" onClick={fetchRoutes} className="shrink-0 h-7 text-xs px-2.5">
            Retry
          </Button>
        </div>
      )}

      {/* 2. Route Summary Cards (4 Columns) */}
      <RouteSummaryCards routesData={routesData} />

      {/* 3. Main Route Monitoring Grid (Left: Active Routes List, Right: Route Canvas) */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(320px,0.85fr)_minmax(0,1.5fr)] gap-6 items-stretch">
        <ActiveRoutesList
          routes={routes}
          selectedVehicleId={selectedVehicleId}
          onSelectRoute={setSelectedVehicleId}
        />

        <RouteVisualizationCanvas
          networkData={networkPreviewData}
          routes={routes}
          geoData={geoData}
          selectedVehicleId={selectedVehicleId}
          onSelectVehicle={setSelectedVehicleId}
        />

      </div>

      {/* 4. Full-Width Selected Route Details */}
      <SelectedRouteDetails selectedRoute={selectedRoute} />
    </div>
  )
}

export default LiveRoutes
