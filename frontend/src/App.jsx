import { useState, useEffect, useCallback } from 'react'
import './App.css'

const FEATURES = [
  {
    icon: '⚛️',
    name: 'Quantum PSO Optimiser',
    desc: 'QPSO-based solver adapted for discrete multi-vehicle routing on classical hardware.',
  },
  {
    icon: '🗺️',
    name: 'Weighted Graph Engine',
    desc: 'Transport network as a graph with distance, travel time, congestion and road-status edges.',
  },
  {
    icon: '🚛',
    name: 'Multi-Vehicle VRP',
    desc: 'Capacity-constrained routing across a fleet, with depot start/end and full customer coverage.',
  },
  {
    icon: '⚡',
    name: 'Dynamic Re-optimisation',
    desc: 'Incidents trigger selective QPSO re-runs on only the affected vehicles — others stay unchanged.',
  },
]

/**
 * HealthStatus – fetches GET /api/health and renders the result.
 * The Vite dev proxy strips /api and forwards to http://localhost:8000.
 */
function HealthStatus() {
  const [state, setState] = useState({ phase: 'idle', data: null, error: null })

  const check = useCallback(async () => {
    setState({ phase: 'loading', data: null, error: null })
    try {
      const res = await fetch('/api/health')
      if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`)
      const json = await res.json()
      setState({ phase: 'ok', data: json, error: null })
    } catch (err) {
      setState({ phase: 'error', data: null, error: err.message })
    }
  }, [])

  useEffect(() => { check() }, [check])

  const dotClass = `status-dot ${state.phase === 'loading' ? 'loading' : state.phase === 'ok' ? 'ok' : state.phase === 'error' ? 'error' : ''}`

  return (
    <div className="status-card" id="health-status-card">
      <div className="status-card-header">
        <span className="status-card-title">Backend Health Check</span>
        <span className={dotClass} title={state.phase} />
      </div>

      {state.phase === 'loading' && (
        <p className="status-value" id="health-loading">Contacting http://localhost:8000/health …</p>
      )}

      {state.phase === 'ok' && (
        <div className="status-value" id="health-ok">
          <pre>{JSON.stringify(state.data, null, 2)}</pre>
        </div>
      )}

      {state.phase === 'error' && (
        <div id="health-error">
          <p className="status-error">⚠ {state.error}</p>
          <p className="status-error" style={{ marginTop: '0.35rem', fontSize: '0.78rem', opacity: 0.7 }}>
            Make sure the FastAPI server is running on port 8000.
          </p>
          <button className="retry-btn" onClick={check} id="health-retry-btn">↻ Retry</button>
        </div>
      )}
    </div>
  )
}

export default function App() {
  return (
    <div className="app">
      {/* ── Navigation ── */}
      <nav className="navbar" id="main-nav">
        <div className="navbar-logo">
          <div className="navbar-logo-icon">Q</div>
          <span className="navbar-title">Q-Route</span>
        </div>
        <span className="navbar-subtitle">SIH 2026 · PS 26137 · Transportation &amp; Logistics</span>
      </nav>

      {/* ── Hero ── */}
      <main className="hero" id="main-content">
        <div className="hero-badge">🏆 Smart India Hackathon 2026</div>

        <h1 className="hero-title" id="page-heading">
          Smart Fleet Routing<br />
          <span className="hero-title-gradient">Powered by QPSO</span>
        </h1>

        <p className="hero-desc">
          Q-Route models urban transport networks as weighted graphs and solves
          the constrained Multi-Vehicle VRP using Quantum Particle Swarm
          Optimisation — with real-time, incident-driven selective re-routing.
        </p>

        {/* Live health check */}
        <HealthStatus />

        {/* Feature overview */}
        <div className="features" id="features-grid">
          {FEATURES.map((f) => (
            <div className="feature-card" key={f.name} id={`feature-${f.name.toLowerCase().replace(/\s+/g, '-')}`}>
              <div className="feature-icon">{f.icon}</div>
              <div className="feature-name">{f.name}</div>
              <div className="feature-desc">{f.desc}</div>
            </div>
          ))}
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="footer" id="page-footer">
        Q-Route · Problem Statement 26137 · Theme: Transportation &amp; Logistics
      </footer>
    </div>
  )
}
