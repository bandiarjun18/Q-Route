import { useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

/**
 * Color palette for rendering independent multi-vehicle routes.
 */
const VEHICLE_COLORS = [
  '#38bdf8', // Sky Blue
  '#818cf8', // Indigo
  '#34d399', // Emerald
  '#f472b6', // Pink
  '#fbbf24', // Amber
  '#a78bfa', // Purple
]

/**
 * Create custom HTML DivIcon for Depot markers.
 */
function createDepotIcon(depotId) {
  return L.divIcon({
    className: 'custom-depot-icon',
    html: `<div style="display:flex;align-items:center;justify-content:center;background:#f59e0b;color:#0f172a;font-weight:700;font-size:11px;border-radius:9999px;width:30px;height:30px;border:2px solid #ffffff;box-shadow:0 3px 10px rgba(0,0,0,0.5);">D#${depotId}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15],
  })
}

/**
 * Create custom HTML DivIcon for Customer delivery markers.
 */
function createCustomerIcon(customerId) {
  return L.divIcon({
    className: 'custom-customer-icon',
    html: `<div style="display:flex;align-items:center;justify-content:center;background:#10b981;color:#ffffff;font-weight:700;font-size:10px;border-radius:9999px;width:24px;height:24px;border:2px solid #ffffff;box-shadow:0 2px 8px rgba(0,0,0,0.4);">C#${customerId}</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  })
}

/**
 * Helper component to automatically fit map bounds when geographic data updates.
 */
function MapBoundsController({ bounds, center }) {
  const map = useMap()

  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [45, 45], maxZoom: 16 })
    } else if (center && center.length === 2) {
      map.setView(center, 13)
    }
  }, [bounds, center, map])

  return null
}

export function OSMMapView({
  geoData,
  selectedVehicleId,
  onSelectVehicle,
  className = '',
}) {
  // Compute bounding box containing all markers and routes
  const { allBounds, defaultCenter, depots, customers, routes } = useMemo(() => {
    const dList = geoData?.depots || []
    const cList = geoData?.customers || []
    const rList = geoData?.routes || []

    const coords = []
    dList.forEach((d) => coords.push([d.latitude, d.longitude]))
    cList.forEach((c) => coords.push([c.latitude, c.longitude]))
    rList.forEach((r) => {
      ;(r.coordinates || []).forEach((pt) => coords.push(pt))
    })

    let center = [12.975, 77.598]
    if (geoData?.center && geoData.center.length === 2) {
      center = geoData.center
    } else if (coords.length > 0) {
      const avgLat = coords.reduce((acc, pt) => acc + pt[0], 0) / coords.length
      const avgLon = coords.reduce((acc, pt) => acc + pt[1], 0) / coords.length
      center = [avgLat, avgLon]
    }

    return {
      allBounds: coords,
      defaultCenter: center,
      depots: dList,
      customers: cList,
      routes: rList,
    }
  }, [geoData])


  return (
    <div className={`relative w-full h-full min-h-[440px] rounded-xl overflow-hidden bg-slate-950 border border-slate-800 flex flex-col ${className}`}>
      {/* 1. Leaflet Map Container */}
      <div className="relative flex-1 w-full h-full">
        <MapContainer
          center={defaultCenter}
          zoom={13}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%', minHeight: '440px', background: '#090d16' }}
        >
          <MapBoundsController bounds={allBounds} center={defaultCenter} />

          {/* Standard OpenStreetMap Tile Layer */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* 2. Route Polylines */}
          {routes.map((route, idx) => {
            const coords = route.coordinates || []
            if (coords.length < 2) return null

            const isSelected = route.vehicle_id === selectedVehicleId
            const color = isSelected
              ? '#38bdf8'
              : VEHICLE_COLORS[idx % VEHICLE_COLORS.length]

            return (
              <Polyline
                key={`route-polyline-${route.vehicle_id}`}
                positions={coords}
                pathOptions={{
                  color,
                  weight: isSelected ? 5 : 3,
                  opacity: isSelected ? 1.0 : 0.75,
                  dashArray: isSelected ? undefined : '6, 4',
                }}
                eventHandlers={{
                  click: () => {
                    if (onSelectVehicle) onSelectVehicle(route.vehicle_id)
                  },
                }}
              >
                <Popup>
                  <div className="text-xs text-slate-800 space-y-1 font-sans">
                    <div className="font-bold text-slate-900 border-b border-slate-200 pb-1">
                      Vehicle #{route.vehicle_id}
                    </div>
                    <div>Distance: {route.total_distance?.toFixed(2)} km</div>
                    <div>Travel Time: {route.total_travel_time?.toFixed(1)} mins</div>
                    <div>Assigned Stops: {route.visit_order?.length || 0}</div>
                  </div>
                </Popup>
              </Polyline>
            )
          })}

          {/* 3. Depot Markers */}
          {depots.map((depot) => (
            <Marker
              key={`depot-marker-${depot.id}`}
              position={[depot.latitude, depot.longitude]}
              icon={createDepotIcon(depot.id)}
            >
              <Popup>
                <div className="text-xs text-slate-800 space-y-1 font-sans">
                  <div className="font-bold text-amber-700 border-b border-slate-200 pb-1">
                    Depot #{depot.id}
                  </div>
                  <div>Primary Fleet Dispatch Center</div>
                  <div className="font-mono text-[11px] text-slate-600">
                    {depot.latitude.toFixed(5)}°, {depot.longitude.toFixed(5)}°
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* 4. Customer Markers */}
          {customers.map((cust) => (
            <Marker
              key={`customer-marker-${cust.id}`}
              position={[cust.latitude, cust.longitude]}
              icon={createCustomerIcon(cust.id)}
            >
              <Popup>
                <div className="text-xs text-slate-800 space-y-1 font-sans">
                  <div className="font-bold text-emerald-700 border-b border-slate-200 pb-1">
                    Customer #{cust.id}
                  </div>
                  <div>Delivery Demand: {cust.demand} units</div>
                  <div>Location Node: #{cust.location_node}</div>
                  <div className="font-mono text-[11px] text-slate-600">
                    {cust.latitude.toFixed(5)}°, {cust.longitude.toFixed(5)}°
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {/* 5. Bottom Map Legend */}
      <div className="px-4 py-2 bg-slate-950/95 border-t border-slate-800/90 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400 z-10">
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 h-1 bg-sky-400 rounded-full" /> Selected Vehicle
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 h-1 bg-indigo-400 rounded-full" /> Other Routes
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Depot ({depots.length})
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" /> Customer ({customers.length})
          </span>
        </div>

        <div className="text-[11px] text-slate-500 font-mono">
          OpenStreetMap & React-Leaflet
        </div>
      </div>
    </div>
  )
}

export default OSMMapView
