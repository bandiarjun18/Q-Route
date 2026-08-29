import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { NetworkIcon, MapPinIcon, ArrowRightIcon } from '../common/Icons.jsx'

export function NetworkPreview({ networkData, className = '' }) {
  const navigate = useNavigate()
  const [selectedNode, setSelectedNode] = useState(null)
  const [zoomLevel, setZoomLevel] = useState(1)

  const nodes = networkData?.nodes || []
  const edges = networkData?.edges || []
  const routes = networkData?.routes || []
  const gridSize = networkData?.grid_size_km || 12

  // Coordinate mapping function for SVG viewBox 0..1000
  const mapCoord = (x, y) => {
    const padding = 55
    const usable = 1000 - padding * 2
    const px = padding + (x / gridSize) * usable
    const py = 1000 - (padding + (y / gridSize) * usable)
    return { x: px, y: py }
  }

  return (
    <Card className={`flex flex-col justify-between h-full ${className}`}>
      {/* Card Header */}
      <CardHeader>
        <div>
          <CardTitle>Transportation Network Preview</CardTitle>
          <CardDescription>
            Spatial topological graph preview
          </CardDescription>
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="text-xs h-8 px-3"
          rightIcon={<ArrowRightIcon className="w-3.5 h-3.5" />}
          onClick={() => navigate('/routes')}
        >
          View Full Map
        </Button>
      </CardHeader>

      {/* Card Content Area */}
      <CardContent className="p-4 sm:p-5 flex-1 flex flex-col justify-center">
        <div className="relative w-full h-[340px] sm:h-[360px] rounded-xl bg-slate-950/90 border border-slate-800/80 overflow-hidden flex flex-col justify-between select-none">
          {nodes.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-8 bg-slate-950/90">
              <div className="max-w-sm w-full text-center space-y-4 flex flex-col items-center">
                <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-blue-400 shadow-xs">
                  <NetworkIcon className="w-6 h-6" />
                </div>

                <div className="space-y-1.5">
                  <h3 className="text-base font-semibold text-slate-100">
                    Build your transportation network
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-400 leading-relaxed max-w-xs mx-auto">
                    Generate nodes and road connections before configuring your fleet.
                  </p>
                </div>

                <div className="pt-1 space-y-2 flex flex-col items-center">
                  <Button variant="primary" size="md" onClick={() => navigate('/network')}>
                    Configure Network
                  </Button>
                  <span className="text-xs text-slate-500">Next step: Configure your fleet</span>
                </div>
              </div>
            </div>
          ) : (
            <>
              {/* Top Bar: Controls */}
              <div className="px-3.5 py-2 flex items-center justify-between gap-3 text-xs text-slate-400 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-xs z-10">
                <div className="flex items-center gap-2">
                  <MapPinIcon className="w-3.5 h-3.5 text-blue-400" />
                  <span className="font-medium text-slate-300">Spatial Topology</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-slate-400 font-mono text-[11px]">
                    {nodes.length} nodes, {edges.length} edges
                  </span>
                </div>

                <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded p-0.5">
                  <button
                    type="button"
                    onClick={() => setZoomLevel((z) => Math.min(z + 0.2, 2.0))}
                    className="px-2 py-0.5 text-xs text-slate-300 hover:text-white transition-colors cursor-pointer"
                    title="Zoom in"
                  >
                    +
                  </button>
                  <button
                    type="button"
                    onClick={() => setZoomLevel((z) => Math.max(z - 0.2, 0.8))}
                    className="px-2 py-0.5 text-xs text-slate-300 hover:text-white transition-colors cursor-pointer"
                    title="Zoom out"
                  >
                    −
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setZoomLevel(1)
                      setSelectedNode(null)
                    }}
                    className="px-2 py-0.5 text-xs text-slate-400 hover:text-slate-200 border-l border-slate-800 transition-colors cursor-pointer"
                    title="Reset zoom"
                  >
                    Reset
                  </button>
                </div>
              </div>

              {/* SVG Map Canvas */}
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
                    {/* Background Grid Lines */}
                    {Array.from({ length: 11 }).map((_, i) => (
                      <g key={`grid-${i}`} opacity="0.08">
                        <line x1={i * 100} y1="0" x2={i * 100} y2="1000" stroke="#64748b" strokeDasharray="3,3" />
                        <line x1="0" y1={i * 100} x2="1000" y2={i * 100} stroke="#64748b" strokeDasharray="3,3" />
                      </g>
                    ))}

                    {/* 1. Graph Edges */}
                    {edges.map((edge, idx) => {
                      const u = nodes.find((n) => n.id === edge.u)
                      const v = nodes.find((n) => n.id === edge.v)
                      if (!u || !v) return null
                      const p1 = mapCoord(u.x, u.y)
                      const p2 = mapCoord(v.x, v.y)

                      return (
                        <line
                          key={`edge-${idx}`}
                          x1={p1.x}
                          y1={p1.y}
                          x2={p2.x}
                          y2={p2.y}
                          stroke={edge.congestion_factor > 1.1 ? '#f59e0b' : '#334155'}
                          strokeWidth={1.5}
                          opacity={0.6}
                        />
                      )
                    })}

                    {/* 2. Vehicle Route Lines */}
                    {routes.map((r, idx) => {
                      const points = r.node_sequence
                        ?.map((nId) => {
                          const node = nodes.find((n) => n.id === nId)
                          if (!node) return null
                          const pt = mapCoord(node.x, node.y)
                          return `${pt.x},${pt.y}`
                        })
                        .filter(Boolean)
                        .join(' ')

                      if (!points) return null

                      return (
                        <polyline
                          key={`route-${idx}`}
                          points={points}
                          fill="none"
                          stroke={r.color || '#3b82f6'}
                          strokeWidth={2.5}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          opacity={0.85}
                        />
                      )
                    })}

                    {/* 3. Graph Nodes */}
                    {nodes.map((node) => {
                      const pt = mapCoord(node.x, node.y)
                      const isDepot = node.node_type === 'depot'
                      const isCust = node.node_type === 'customer'
                      const isSelected = selectedNode?.id === node.id

                      return (
                        <g
                          key={`node-${node.id}`}
                          onClick={() => setSelectedNode(node)}
                          className="cursor-pointer"
                        >
                          {isSelected && (
                            <circle
                              cx={pt.x}
                              cy={pt.y}
                              r={isDepot ? 16 : 12}
                              fill="none"
                              stroke="#38bdf8"
                              strokeWidth="2"
                              strokeDasharray="3,2"
                            />
                          )}

                          <circle
                            cx={pt.x}
                            cy={pt.y}
                            r={isDepot ? 9 : isCust ? 7 : 4.5}
                            fill={isDepot ? '#f59e0b' : isCust ? '#10b981' : '#64748b'}
                            stroke="#0f172a"
                            strokeWidth="1.5"
                          />

                          <text
                            x={pt.x}
                            y={pt.y - (isDepot ? 12 : 10)}
                            textAnchor="middle"
                            fill={isDepot ? '#fbbf24' : isCust ? '#34d399' : '#94a3b8'}
                            fontSize={isDepot ? '12' : '10'}
                            fontWeight="bold"
                          >
                            {isDepot ? `DEPOT #${node.id}` : `#${node.id}`}
                          </text>

                          {isCust && node.demand != null && (
                            <text
                              x={pt.x}
                              y={pt.y + 14}
                              textAnchor="middle"
                              fill="#cbd5e1"
                              fontSize="8.5"
                              fontWeight="bold"
                            >
                              {node.demand}u
                            </text>
                          )}
                        </g>
                      )
                    })}
                  </svg>
                </div>

                {/* Selected Node Tooltip */}
                {selectedNode && (
                  <div className="absolute bottom-3 left-3 bg-slate-900/95 border border-slate-700 rounded-lg p-3 shadow-lg backdrop-blur-md text-xs space-y-1 z-20 min-w-[190px]">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-1">
                      <span className="font-semibold text-slate-100">
                        Node #{selectedNode.id} ({selectedNode.node_type})
                      </span>
                      <button
                        type="button"
                        onClick={() => setSelectedNode(null)}
                        className="text-slate-400 hover:text-white p-0.5 cursor-pointer"
                      >
                        ✕
                      </button>
                    </div>
                    <div className="text-slate-300 text-xs space-y-0.5 font-mono">
                      <div>Coords: ({selectedNode.x.toFixed(1)}, {selectedNode.y.toFixed(1)}) km</div>
                      {selectedNode.node_type === 'customer' && (
                        <div className="text-emerald-400 font-medium">
                          Demand: {selectedNode.demand ?? 0} units
                        </div>
                      )}
                      {selectedNode.node_type === 'depot' && (
                        <div className="text-amber-400 font-medium">Primary Home Depot</div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom Legend Footer */}
              <div className="px-4 py-2 bg-slate-950/95 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400 z-10">
                <div className="flex items-center gap-3.5">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400" /> Depot
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" /> Customer
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-500" /> Intersection
                  </span>
                </div>
                <div className="text-xs text-slate-500 font-mono">
                  Grid: {gridSize}km
                </div>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default NetworkPreview
