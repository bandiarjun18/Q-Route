import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Badge } from '../ui/Badge.jsx'
import { RoutesIcon, MapPinIcon } from '../common/Icons.jsx'

export function RouteVisualizationCanvas({
  networkData,
  routes = [],
  selectedVehicleId,
}) {
  const navigate = useNavigate()
  const [zoomLevel, setZoomLevel] = useState(1)

  const nodes = networkData?.nodes || []
  const edges = networkData?.edges || []
  const gridSize = networkData?.grid_size_km || 10

  const mapCoord = (x, y) => {
    const padding = 60
    const usable = 1000 - padding * 2
    const px = padding + (x / gridSize) * usable
    const py = 1000 - (padding + (y / gridSize) * usable)
    return { x: px, y: py }
  }

  // Find the selected route object
  const selectedRoute = routes.find((r) => r.vehicle_id === selectedVehicleId)

  // Determine which routes traverse each edge
  const getEdgeRouteInfo = (uId, vId) => {
    const activeRouteIds = []
    let isSelectedTraversed = false

    routes.forEach((r) => {
      const seq = r.node_sequence || []
      for (let i = 0; i < seq.length - 1; i++) {
        if (
          (seq[i] === uId && seq[i + 1] === vId) ||
          (seq[i] === vId && seq[i + 1] === uId)
        ) {
          activeRouteIds.push(r.vehicle_id)
          if (r.vehicle_id === selectedVehicleId) {
            isSelectedTraversed = true
          }
        }
      }
    })

    return { activeRouteIds, isSelectedTraversed }
  }

  return (
    <Card className="flex flex-col h-full">
      {/* Header */}
      <CardHeader>
        <div>
          <CardTitle>Route Visualization</CardTitle>
          <CardDescription>
            Spatial network map with multi-vehicle path overlays
          </CardDescription>
        </div>

        <div className="flex items-center gap-2">
          {selectedRoute && (
            <Badge variant="info" size="sm">
              Highlighting Vehicle #{selectedRoute.vehicle_id}
            </Badge>
          )}
        </div>
      </CardHeader>

      {/* Content */}
      <CardContent className="p-4 sm:p-5 flex-1 flex flex-col justify-between">
        <div className="relative w-full h-[440px] sm:h-[480px] lg:h-[500px] rounded-xl bg-slate-950/95 border border-slate-800/80 overflow-hidden flex flex-col justify-between select-none">
          {routes.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-8 bg-slate-950/95 text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-blue-400">
                <RoutesIcon className="w-6 h-6" />
              </div>
              <div className="space-y-1 max-w-sm">
                <h4 className="text-base font-semibold text-slate-100">No route paths to display</h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Execute route optimization to compute and render live spatial path trajectories.
                </p>
              </div>
              <div className="pt-1">
                <Button variant="primary" size="sm" onClick={() => navigate('/optimization')}>
                  Run Optimization
                </Button>
              </div>
            </div>
          ) : (
            <>
              {/* Top Toolbar */}
              <div className="px-4 py-2.5 flex items-center justify-between gap-3 text-xs text-slate-400 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-xs z-10">
                <div className="flex items-center gap-2">
                  <MapPinIcon className="w-4 h-4 text-blue-400" />
                  <span className="font-medium text-slate-200">Active Path Geometry</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-slate-400 font-mono">
                    {routes.length} Active Routes
                  </span>
                </div>

                <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-0.5">
                  <button
                    type="button"
                    onClick={() => setZoomLevel((z) => Math.min(z + 0.2, 2.5))}
                    className="px-2.5 py-1 text-xs text-slate-300 hover:text-white transition-colors cursor-pointer"
                    title="Zoom in"
                  >
                    +
                  </button>
                  <button
                    type="button"
                    onClick={() => setZoomLevel((z) => Math.max(z - 0.2, 0.7))}
                    className="px-2.5 py-1 text-xs text-slate-300 hover:text-white transition-colors cursor-pointer"
                    title="Zoom out"
                  >
                    −
                  </button>
                  <button
                    type="button"
                    onClick={() => setZoomLevel(1)}
                    className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200 border-l border-slate-800 transition-colors cursor-pointer"
                    title="Reset zoom"
                  >
                    Reset Zoom
                  </button>
                </div>
              </div>

              {/* SVG Canvas */}
              <div className="relative flex-1 w-full h-full overflow-hidden">
                <div
                  className="w-full h-full"
                  style={{
                    transform: `scale(${zoomLevel})`,
                    transformOrigin: 'center center',
                    transition: 'transform 0.15s ease-out',
                  }}
                >
                  <svg
                    viewBox="0 0 1000 1000"
                    className="w-full h-full"
                    preserveAspectRatio="xMidYMid meet"
                  >
                    {/* Background Grid */}
                    {Array.from({ length: 11 }).map((_, i) => (
                      <g key={`grid-${i}`} opacity="0.07">
                        <line x1={i * 100} y1="0" x2={i * 100} y2="1000" stroke="#64748b" strokeDasharray="3,3" />
                        <line x1="0" y1={i * 100} x2="1000" y2={i * 100} stroke="#64748b" strokeDasharray="3,3" />
                      </g>
                    ))}

                    {/* 1. Underlying Base Road Network */}
                    {edges.map((edge, idx) => {
                      const u = nodes.find((n) => n.id === edge.u)
                      const v = nodes.find((n) => n.id === edge.v)
                      if (!u || !v) return null
                      const p1 = mapCoord(u.x, u.y)
                      const p2 = mapCoord(v.x, v.y)
                      const { activeRouteIds } = getEdgeRouteInfo(edge.u, edge.v)

                      if (activeRouteIds.length > 0) return null

                      return (
                        <line
                          key={`base-edge-${idx}`}
                          x1={p1.x}
                          y1={p1.y}
                          x2={p2.x}
                          y2={p2.y}
                          stroke="#1e293b"
                          strokeWidth="1.2"
                          opacity="0.4"
                        />
                      )
                    })}

                    {/* 2. Route Path Overlays */}
                    {edges.map((edge, idx) => {
                      const u = nodes.find((n) => n.id === edge.u)
                      const v = nodes.find((n) => n.id === edge.v)
                      if (!u || !v) return null
                      const p1 = mapCoord(u.x, u.y)
                      const p2 = mapCoord(v.x, v.y)
                      const { isSelectedTraversed, activeRouteIds } = getEdgeRouteInfo(edge.u, edge.v)

                      if (activeRouteIds.length === 0) return null

                      return (
                        <line
                          key={`route-edge-${idx}`}
                          x1={p1.x}
                          y1={p1.y}
                          x2={p2.x}
                          y2={p2.y}
                          stroke={
                            isSelectedTraversed
                              ? '#38bdf8'
                              : '#6366f1'
                          }
                          strokeWidth={isSelectedTraversed ? 3.5 : 2}
                          strokeDasharray={isSelectedTraversed ? undefined : '5,3'}
                          opacity={isSelectedTraversed ? 1 : 0.6}
                        />
                      )
                    })}

                    {/* 3. Graph Nodes */}
                    {nodes.map((node) => {
                      const pt = mapCoord(node.x, node.y)
                      const isDepot = node.node_type === 'depot'
                      const isCust = node.node_type === 'customer'
                      const isSelectedRouteNode =
                        selectedRoute?.node_sequence?.includes(node.id)

                      return (
                        <g
                          key={`node-${node.id}`}
                          className="cursor-pointer"
                        >
                          {isSelectedRouteNode && (
                            <circle
                              cx={pt.x}
                              cy={pt.y}
                              r={isDepot ? 18 : 14}
                              fill="none"
                              stroke="#38bdf8"
                              strokeWidth="2"
                              strokeDasharray="4,3"
                            />
                          )}

                          <circle
                            cx={pt.x}
                            cy={pt.y}
                            r={isDepot ? 10 : isCust ? 8 : 5}
                            fill={isDepot ? '#f59e0b' : isCust ? '#10b981' : '#64748b'}
                            stroke="#0f172a"
                            strokeWidth="2"
                          />

                          <text
                            x={pt.x}
                            y={pt.y - (isDepot ? 14 : 12)}
                            textAnchor="middle"
                            fill={isDepot ? '#fbbf24' : isCust ? '#34d399' : '#94a3b8'}
                            fontSize={isDepot ? '13' : '11'}
                            fontWeight="bold"
                          >
                            {isDepot ? `DEPOT #${node.id}` : `#${node.id}`}
                          </text>
                        </g>
                      )
                    })}
                  </svg>
                </div>
              </div>

              {/* Bottom Canvas Legend */}
              <div className="px-4 py-2.5 bg-slate-950/95 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400 z-10">
                <div className="flex items-center gap-4">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-3 h-1 bg-sky-400 rounded-full" /> Selected Route
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-3 h-1 bg-indigo-500 rounded-full" /> Other Active Routes
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Depot
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" /> Customer
                  </span>
                </div>
                <div className="text-xs text-slate-500 font-mono">
                  Coordinate Domain: [0..{gridSize} km]
                </div>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default RouteVisualizationCanvas
