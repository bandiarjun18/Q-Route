import { useState, useEffect, useCallback } from 'react'
import { PageHeader } from '../components/ui/PageHeader.jsx'
import { Button } from '../components/ui/Button.jsx'
import { Select } from '../components/ui/Select.jsx'
import { Input } from '../components/ui/Input.jsx'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card.jsx'
import { RouteSummaryCards } from '../components/routes/RouteSummaryCards.jsx'
import { ActiveRoutesList } from '../components/routes/ActiveRoutesList.jsx'
import { RouteVisualizationCanvas } from '../components/routes/RouteVisualizationCanvas.jsx'
import { SelectedRouteDetails } from '../components/routes/SelectedRouteDetails.jsx'
import { RefreshIcon, IncidentsIcon, CheckCircleIcon } from '../components/common/Icons.jsx'
import { getCurrentRoutes, getGeographicRoutes, registerIncident } from '../api/qroute.js'
import { networkPreviewData } from '../data/dashboardData.js'

const INCIDENT_TYPES = [
  { value: 'ROAD_CLOSURE', label: 'Road Closure (Full Blockage)' },
  { value: 'ACCIDENT', label: 'Accident (Vehicle Collision)' },
  { value: 'CONSTRUCTION', label: 'Construction (Work Zone Delay)' },
  { value: 'OBSTRUCTION', label: 'Obstruction (Hazard / Debris)' },
]

const SEVERITIES = [
  { value: 'HIGH', label: 'High (×2.0 Delay)' },
  { value: 'CRITICAL', label: 'Critical (×3.0 Delay)' },
  { value: 'MEDIUM', label: 'Medium (×1.5 Delay)' },
  { value: 'LOW', label: 'Low (×1.2 Delay)' },
]

export function LiveRoutes() {
  const [routesData, setRoutesData] = useState(null)
  const [geoData, setGeoData] = useState(null)
  const [selectedVehicleId, setSelectedVehicleId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isRerouting, setIsRerouting] = useState(false)
  const [error, setError] = useState(null)

  // Incident reporting modal / form state
  const [showIncidentForm, setShowIncidentForm] = useState(false)
  const [edgeU, setEdgeU] = useState('')
  const [edgeV, setEdgeV] = useState('')
  const [incidentType, setIncidentType] = useState('ROAD_CLOSURE')
  const [severity, setSeverity] = useState('HIGH')
  const [incidentDesc, setIncidentDesc] = useState('Emergency road blockage reported')
  const [incidentSuccessInfo, setIncidentSuccessInfo] = useState(null)

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
        const errMsg = err?.message || ''
        if (
          errMsg.includes('409') ||
          errMsg.toLowerCase().includes('not run') ||
          errMsg.toLowerCase().includes('not configured') ||
          errMsg.toLowerCase().includes('no active')
        ) {
          setRoutesData({ total_active: 0, routes: [] })
          setSelectedVehicleId(null)
        } else {
          setError(errMsg || 'Failed to retrieve active routes from backend API.')
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
            } else {
              setSelectedVehicleId(null)
            }
          } else {
            const err = routesRes.reason
            const errMsg = err?.message || ''
            if (
              errMsg.includes('409') ||
              errMsg.toLowerCase().includes('not run') ||
              errMsg.toLowerCase().includes('not configured') ||
              errMsg.toLowerCase().includes('no active')
            ) {
              setRoutesData({ total_active: 0, routes: [] })
              setSelectedVehicleId(null)
            } else {
              setError(errMsg || 'Failed to retrieve active routes from backend API.')
            }
          }
          if (geoRes.status === 'fulfilled') {
            setGeoData(geoRes.value)
          } else {
            setGeoData(null)
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

  // Extract edges from active routes for quick selection
  const routes = routesData?.routes || []
  const activeRouteEdges = []
  routes.forEach((r) => {
    const seq = r.node_sequence || []
    for (let i = 0; i < seq.length - 1; i++) {
      const u = seq[i]
      const v = seq[i + 1]
      if (!activeRouteEdges.some((e) => e.u === u && e.v === v)) {
        activeRouteEdges.push({ u, v, vehicle_id: r.vehicle_id })
      }
    }
  })

  // Handle live incident submission & dynamic rerouting
  const handleLiveIncidentSubmit = async (e) => {
    e.preventDefault()
    if (!edgeU || !edgeV) {
      setError('Please select or specify valid start and end nodes for the road segment.')
      return
    }

    setIsRerouting(true)
    setError(null)
    setIncidentSuccessInfo(null)

    try {
      const res = await registerIncident({
        edge_u: edgeU,
        edge_v: edgeV,
        incident_type: incidentType,
        severity,
        description: incidentDesc,
      })

      setIncidentSuccessInfo({
        edge_u: res.edge_u,
        edge_v: res.edge_v,
        incident_type: res.incident_type,
        is_closure: res.is_closure,
        n_affected: res.n_affected,
        affected_vehicle_ids: res.affected_vehicle_ids,
        unaffected_count: res.unaffected_route_count,
      })

      setShowIncidentForm(false)
      // Refresh live routes and geographic visualization
      await fetchRoutes()
    } catch (err) {
      setError(err?.message || 'Failed to register incident and perform dynamic rerouting.')
    } finally {
      setIsRerouting(false)
    }
  }

  const selectedRoute = routes.find((r) => r.vehicle_id === selectedVehicleId)

  return (
    <div className="space-y-6 sm:space-y-8 w-full">
      {/* 1. Page Header with Actions */}
      <PageHeader
        title="Live Routes"
        subtitle="Monitor active vehicle routes, road disruptions, and dynamic QPSO re-routing."
        actions={
          <div className="flex items-center gap-2.5">
            <Button
              variant={showIncidentForm ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => {
                setShowIncidentForm(!showIncidentForm)
                if (!edgeU && activeRouteEdges.length > 0) {
                  setEdgeU(activeRouteEdges[0].u)
                  setEdgeV(activeRouteEdges[0].v)
                }
              }}
              leftIcon={<IncidentsIcon className="w-3.5 h-3.5 text-amber-400" />}
              className="text-xs h-8 px-3"
            >
              {showIncidentForm ? 'Close Incident Form' : 'Report Incident'}
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={fetchRoutes}
              isLoading={isLoading || isRerouting}
              leftIcon={<RefreshIcon className="w-3.5 h-3.5" />}
              className="text-xs h-8 px-3"
            >
              {isLoading || isRerouting ? 'Updating...' : 'Refresh'}
            </Button>
          </div>
        }
      />

      {/* Post-Incident Reroute Notification Banner */}
      {incidentSuccessInfo && (
        <div className="p-4 bg-emerald-950/80 border border-emerald-800/80 rounded-xl text-emerald-200 text-xs sm:text-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg">
          <div className="flex items-start gap-2.5 min-w-0">
            <CheckCircleIcon className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <div className="font-semibold text-emerald-100">
                Road Incident Registered & Selective Rerouting Complete
              </div>
              <p className="text-xs text-emerald-300/90 leading-relaxed">
                Segment N{incidentSuccessInfo.edge_u} → N{incidentSuccessInfo.edge_v} (
                {incidentSuccessInfo.is_closure ? 'Road Closure' : incidentSuccessInfo.incident_type}) ·{' '}
                <span className="font-bold text-white">{incidentSuccessInfo.n_affected}</span> vehicles
                rerouted ({incidentSuccessInfo.affected_vehicle_ids.length > 0 ? incidentSuccessInfo.affected_vehicle_ids.join(', ') : 'none affected'}). Map and active route telemetry updated.
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIncidentSuccessInfo(null)}
            className="shrink-0 h-7 text-xs px-2.5 text-emerald-400 hover:text-emerald-200 border border-emerald-800/60"
          >
            Dismiss
          </Button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-3.5 bg-rose-950/80 border border-rose-800/80 rounded-lg text-rose-300 text-xs sm:text-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="font-semibold">Operation Notice:</span>
            <span className="truncate">{error}</span>
          </div>
          <Button variant="danger" size="sm" onClick={fetchRoutes} className="shrink-0 h-7 text-xs px-2.5">
            Retry
          </Button>
        </div>
      )}

      {/* Collapsible Quick Incident Registration Drawer */}
      {showIncidentForm && (
        <Card className="w-full border-amber-500/40 bg-slate-950/95 shadow-xl ring-1 ring-amber-500/20">
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-amber-600/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
                <IncidentsIcon className="w-4 h-4" />
              </div>
              <div>
                <CardTitle>Report Road Incident & Trigger Live Rerouting</CardTitle>
                <CardDescription>
                  Simulate dynamic road disruptions to observe instant selective rerouting and database persistence.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-5 space-y-4">
            <form onSubmit={handleLiveIncidentSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                {activeRouteEdges.length > 0 ? (
                  <Select
                    label="Active Route Segment"
                    value={`${edgeU}-${edgeV}`}
                    onChange={(e) => {
                      const [u, v] = e.target.value.split('-')
                      setEdgeU(u)
                      setEdgeV(v)
                    }}
                    disabled={isRerouting}
                  >
                    {activeRouteEdges.map((ed, idx) => (
                      <option key={`edge-opt-${idx}`} value={`${ed.u}-${ed.v}`}>
                        N{ed.u} → N{ed.v} (Veh #{ed.vehicle_id})
                      </option>
                    ))}
                  </Select>
                ) : (
                  <>
                    <Input
                      label="Start Node (u)"
                      value={edgeU}
                      onChange={(e) => setEdgeU(e.target.value)}
                      placeholder="e.g. 101 or 0"
                      disabled={isRerouting}
                      required
                    />
                    <Input
                      label="End Node (v)"
                      value={edgeV}
                      onChange={(e) => setEdgeV(e.target.value)}
                      placeholder="e.g. 102 or 1"
                      disabled={isRerouting}
                      required
                    />
                  </>
                )}

                <Select
                  label="Incident Type"
                  value={incidentType}
                  onChange={(e) => setIncidentType(e.target.value)}
                  options={INCIDENT_TYPES}
                  disabled={isRerouting}
                />

                <Select
                  label="Severity"
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  options={SEVERITIES}
                  disabled={isRerouting}
                />

                <div className="flex flex-col justify-end">
                  <Input
                    label="Description"
                    value={incidentDesc}
                    onChange={(e) => setIncidentDesc(e.target.value)}
                    placeholder="e.g. Road flooded"
                    disabled={isRerouting}
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-800/80">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowIncidentForm(false)}
                  disabled={isRerouting}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isRerouting}
                  leftIcon={<IncidentsIcon className="w-3.5 h-3.5" />}
                  className="text-xs font-semibold px-4"
                >
                  {isRerouting ? 'Executing Reroute...' : 'Apply Incident & Re-Optimize'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
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
