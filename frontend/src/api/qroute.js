/**
 * API client for Q-Route backend services.
 * Uses relative `/api` paths handled by the Vite dev server proxy (or same-origin in prod).
 */

const BASE_URL = '/api'

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`
    try {
      const data = await response.json()
      if (data && data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      }
    } catch {
      // Non-JSON error body
    }
    throw new Error(errorDetail)
  }
  return response.json()
}

/**
 * Check backend health status (GET /health)
 */
export async function healthCheck() {
  const res = await fetch(`${BASE_URL}/health`)
  return handleResponse(res)
}

/**
 * Generate a synthetic road network (POST /network)
 */
export async function createNetwork(params = {}) {
  const payload = {
    n_nodes: Number(params.n_nodes ?? 20),
    n_depots: Number(params.n_depots ?? 1),
    n_customers: Number(params.n_customers ?? 6),
    connect_radius_km: Number(params.connect_radius_km ?? 3.5),
    grid_size_km: Number(params.grid_size_km ?? 10.0),
    closed_fraction: Number(params.closed_fraction ?? 0.05),
    seed: params.seed !== undefined && params.seed !== '' ? Number(params.seed) : 42,
  }

  const res = await fetch(`${BASE_URL}/network`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return handleResponse(res)
}

/**
 * Configure vehicles and customer delivery orders (POST /fleet)
 */
export async function configureFleet(payload) {
  const res = await fetch(`${BASE_URL}/fleet`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return handleResponse(res)
}

/**
 * Run QPSO multi-vehicle route optimization (POST /optimize)
 */
export async function runOptimization(params = {}) {
  const payload = {
    n_particles: Number(params.n_particles ?? 20),
    max_iterations: Number(params.max_iterations ?? 100),
    time_budget_seconds:
      params.time_budget_seconds !== undefined &&
      params.time_budget_seconds !== '' &&
      params.time_budget_seconds !== null
        ? Number(params.time_budget_seconds)
        : null,
    seed: params.seed !== undefined && params.seed !== '' ? Number(params.seed) : 42,
    w_time: Number(params.w_time ?? 1.0),
    w_distance: Number(params.w_distance ?? 0.5),
    w_congestion: Number(params.w_congestion ?? 0.3),
  }

  const res = await fetch(`${BASE_URL}/optimize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  return handleResponse(res)
}

/**
 * Retrieve all currently active vehicle routes (GET /routes/current)
 */
export async function getCurrentRoutes() {
  const res = await fetch(`${BASE_URL}/routes/current`)
  return handleResponse(res)
}

/**
 * Register a road incident and trigger dynamic re-optimization (POST /incidents)
 */
export async function registerIncident(payload) {
  const res = await fetch(`${BASE_URL}/incidents`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      edge_u: Number(payload.edge_u),
      edge_v: Number(payload.edge_v),
      incident_type: payload.incident_type || 'ACCIDENT',
      severity: payload.severity || 'MEDIUM',
      description: payload.description || '',
    }),
  })
  return handleResponse(res)
}

/**
 * Retrieve QPSO convergence telemetry history (GET /analytics/convergence)
 */
export async function getConvergenceHistory() {
  const res = await fetch(`${BASE_URL}/analytics/convergence`)
  return handleResponse(res)
}

export default {
  healthCheck,
  createNetwork,
  configureFleet,
  runOptimization,
  getCurrentRoutes,
  registerIncident,
  getConvergenceHistory,
}
