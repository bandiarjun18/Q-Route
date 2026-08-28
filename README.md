# Q-Route

**Smart India Hackathon 2026 · Problem Statement 26137 · Theme: Transportation & Logistics**

## What is Q-Route?

Q-Route is a fleet routing and logistics optimisation platform that models a city's transportation network as a weighted graph and solves the constrained Multi-Vehicle Vehicle Routing Problem (VRP). The core solver is **Quantum Particle Swarm Optimisation (QPSO)** — a quantum-inspired metaheuristic that runs on ordinary classical hardware. Routes are refined with a 2-opt local search pass. The system responds to simulated real-time incidents (accidents, road closures, congestion) by selectively re-optimising only the vehicles whose routes are affected, leaving all other active routes unchanged.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite 6 + Tailwind CSS + React-Leaflet (maps) + Recharts (charts) |
| Backend | Python 3.11+ · FastAPI · Uvicorn |
| Optimisation | QPSO + 2-opt · NumPy · Pandas |
| Graph & Routing | NetworkX · shortest-path algorithms |
| Database / Data | PostgreSQL · JSON / CSV synthetic datasets |

## Project Structure

```
Q-Route/
├── backend/
│   ├── app/
│   │   ├── graph/        # Transportation graph engine
│   │   ├── vrp/          # Fleet & customer model, VRP formulation
│   │   ├── qpso/         # QPSO optimiser + 2-opt refinement
│   │   ├── traffic/      # Traffic simulation
│   │   ├── incidents/    # Incident detection & affected-vehicle logic
│   │   ├── routes/       # Route management & ETA
│   │   └── main.py       # FastAPI application entry point
│   ├── tests/
│   └── requirements.txt
├── frontend/             # React + Vite application
├── data/                 # Synthetic datasets (JSON / CSV)
├── experiments/          # Experiment scripts & configs
├── results/              # Experiment outputs
├── docs/                 # Architecture docs & diagrams
└── README.md
```

## How to Run Locally

### Backend

```bash
# 1. Create and activate a virtual environment
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the development server (auto-reload on file changes)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at **http://localhost:8000**.  
Interactive docs (Swagger UI): **http://localhost:8000/docs**  
Health check: **http://localhost:8000/health**

### Frontend

```bash
# From the project root
cd frontend

# Install Node dependencies (first time only)
npm install

# Start the Vite dev server
npm run dev
```

The frontend will be available at **http://localhost:5173**.

> **Note:** Start the backend first so the frontend's health-check fetch succeeds on load.

## Development Workflow

- One milestone at a time — do not begin the next until the current one is verified.
- Commit after every milestone.
- All route segments must use valid graph paths; closed edges are never inserted into feasible routes.
- Objective function: `Fitness = wT·TravelTime + wD·Distance + wC·Congestion + Penalty(violations)` — weights are configurable and used consistently across all components.

## License

To be decided.
