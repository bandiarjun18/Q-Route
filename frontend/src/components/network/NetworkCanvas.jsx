import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/Card.jsx'
import { Button } from '../ui/Button.jsx'
import { Badge } from '../ui/Badge.jsx'
import { NetworkIcon, MapPinIcon } from '../common/Icons.jsx'

export function NetworkCanvas({ networkData, onGenerate, isLoading, className = '' }) {
  const [selectedNode, setSelectedNode] = useState(null)
  const [zoomLevel, setZoomLevel] = useState(1)

  const nodes = networkData?.nodes || []
  const edges = networkData?.edges || []
  const gridSize = networkData?.grid_size_km || 10

  // Coordinate mapping function for SVG viewBox 0..1000
  const mapCoord = (x, y) => {
    const padding = 55
    const usable = 1000 - padding * 2
    const px = padding + (x / gridSize) * usable
    const py = 1000 - (padding + (y / gridSize) * usable)
    return { x: px, y: py }
  }

  // Get incident edges connected to a selected node
  const getNodeConnectedEdges = (nodeId) => {
    return edges.filter((e) => e.u === nodeId || e.v === nodeId)
  }

  return (
    <Card className={`w-full ${className}`}>
      {/* Card Header */}
      <CardHeader>
        <div>
          <CardTitle>Transportation Network Map</CardTitle>
          <CardDescription>
            Spatial topological graph visualization with node classifications and road segments
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          {nodes.length > 0 && (
            <Badge variant="info" size="sm">
              {nodes.length} Nodes · {edges.length} Edges
            </Badge>
          )}
        </div>
      </CardHeader>

      {/* Card Content */}
      <CardContent className="p-4 sm:p-5">
        <div className="relative w-full h-[420px] sm:h-[480px] lg:h-[520px] rounded-xl bg-slate-950/95 border border-slate-800/80 overflow-hidden flex flex-col justify-between select-none">
          {nodes.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-8 bg-slate-950/95">
              <div className="max-w-md w-full text-center space-y-4 flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-blue-400 shadow-xs">
                  <NetworkIcon className="w-7 h-7" />
                </div>

                <div className="space-y-1.5">
                  <h3 className="text-lg font-semibold text-slate-100">
                    No transportation network yet
                  </h3>
                  <p className="text-sm text-slate-400 leading-relaxed max-w-sm mx-auto">
                    Generate a network using the configuration panel above to visualize the routing topology.
                  </p>
                </div>

                <div className="pt-2">
                  <Button
                    variant="primary"
                    size="md"
                    onClick={onGenerate}
                    isLoading={isLoading}
                    leftIcon={<NetworkIcon className="w-4 h-4" />}
                  >
                    Generate Network
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <>
              {/* Top Controls Toolbar */}
              <div className="px-4 py-2.5 flex items-center justify-between gap-3 text-xs text-slate-400 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-xs z-10">
                <div className="flex items-center gap-2">
                  <MapPinIcon className="w-4 h-4 text-blue-400" />
                  <span className="font-medium text-slate-200">Topological Coordinate Space</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-slate-400 font-mono">
                    Boundary: [0..{gridSize} km × 0..{gridSize} km]
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
                    onClick={() => {
                      setZoomLevel(1)
                      setSelectedNode(null)
                    }}
                    className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200 border-l border-slate-800 transition-colors cursor-pointer"
                    title="Reset zoom"
                  >
                    Reset Zoom
                  </button>
                </div>
              </div>

              {/* SVG Visualization Canvas */}
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

                    {/* 1. Road Edges */}
                    {edges.map((edge, idx) => {
                      const u = nodes.find((n) => n.id === edge.u)
                      const v = nodes.find((n) => n.id === edge.v)
                      if (!u || !v) return null
                      const p1 = mapCoord(u.x, u.y)
                      const p2 = mapCoord(v.x, v.y)
                      const isClosed = edge.road_status === 'closed'
                      const isSelectedConnected =
                        selectedNode && (selectedNode.id === edge.u || selectedNode.id === edge.v)

                      return (
                        <line
                          key={`edge-${idx}`}
                          x1={p1.x}
                          y1={p1.y}
                          x2={p2.x}
                          y2={p2.y}
                          stroke={
                            isClosed
                              ? '#f43f5e'
                              : isSelectedConnected
                              ? '#38bdf8'
                              : edge.congestion_factor > 1.2
                              ? '#f59e0b'
                              : '#334155'
                          }
                          strokeWidth={isSelectedConnected ? 2.5 : isClosed ? 2 : 1.2}
                          strokeDasharray={isClosed ? '5,4' : undefined}
                          opacity={isClosed ? 0.9 : isSelectedConnected ? 1 : 0.6}
                        />
                      )
                    })}

                    {/* 2. Graph Nodes */}
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
                              r={isDepot ? 18 : 14}
                              fill="none"
                              stroke="#38bdf8"
                              strokeWidth="2.5"
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

                          {/* Coordinates subtitle on node */}
                          <text
                            x={pt.x}
                            y={pt.y + (isDepot ? 18 : 16)}
                            textAnchor="middle"
                            fill="#64748b"
                            fontSize="8"
                            fontFamily="monospace"
                          >
                            ({node.x.toFixed(1)},{node.y.toFixed(1)})
                          </text>
                        </g>
                      )
                    })}
                  </svg>
                </div>

                {/* Node Inspection Tooltip */}
                {selectedNode && (
                  <div className="absolute bottom-4 left-4 bg-slate-900/95 border border-slate-700 rounded-xl p-3.5 shadow-xl backdrop-blur-md text-xs space-y-2 z-20 min-w-[210px]">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`w-2.5 h-2.5 rounded-full ${
                            selectedNode.node_type === 'depot'
                              ? 'bg-amber-400'
                              : selectedNode.node_type === 'customer'
                              ? 'bg-emerald-400'
                              : 'bg-slate-400'
                          }`}
                        />
                        <span className="font-semibold text-slate-100">
                          Node #{selectedNode.id} ({selectedNode.node_type})
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedNode(null)}
                        className="text-slate-400 hover:text-white p-0.5 cursor-pointer"
                      >
                        ✕
                      </button>
                    </div>

                    <div className="text-slate-300 space-y-1 font-mono text-[11px]">
                      <div>Coordinates: ({selectedNode.x.toFixed(2)}, {selectedNode.y.toFixed(2)}) km</div>
                      <div>Connected Edges: {getNodeConnectedEdges(selectedNode.id).length}</div>
                      {selectedNode.node_type === 'depot' && (
                        <div className="text-amber-400 font-semibold pt-0.5">Primary Dispatch Depot</div>
                      )}
                      {selectedNode.node_type === 'customer' && (
                        <div className="text-emerald-400 font-semibold pt-0.5">Customer Delivery Point</div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom Canvas Footer */}
              <div className="px-4 py-2.5 bg-slate-950/95 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400 z-10">
                <div className="flex items-center gap-4">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Depot Node
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" /> Customer Node
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-slate-500" /> Road Intersection
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-3 h-0.5 bg-rose-500" /> Closed Segment
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

export default NetworkCanvas
