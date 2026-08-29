# Q-Route

**Smart India Hackathon 2026 · Problem Statement 26137 · Theme: Transportation & Logistics**

---

## 1. Project Overview

**Q-Route** is an enterprise fleet routing and logistics optimization platform designed for urban and regional transportation networks. It models real-world road infrastructure as directed weighted graphs and solves the constrained Multi-Vehicle Vehicle Routing Problem (VRP).

At the core of Q-Route is **Quantum Particle Swarm Optimization (QPSO)** — a quantum-inspired metaheuristic that operates on classical hardware using delta-potential quantum wave function modeling to explore combinatorial search spaces efficiently without getting trapped in local optima. Generated candidate routes are refined with feasibility repair and a 2-opt local search heuristic. 

When real-time disruptions occur (such as accidents, road closures, construction, or congestion spikes), Q-Route's incident-aware intelligence **selectively re-optimizes only the affected vehicles**, keeping all unaffected routes active and stable.

---

## 2. Key Features

- **Transportation Graph Engine**: Directed graph topology using NetworkX, supporting Euclidean node coordinates, configurable speed limits, congestion multipliers, and dynamic road closures.
- **Constrained Multi-Vehicle VRP**: Strict enforcement of vehicle payload capacities, customer cargo demands, mandatory depot return, and open-edge path continuity.
- **Quantum-Inspired Metaheuristic (QPSO)**: Continuous-space quantum delta-potential particle dynamics decoded into discrete customer visit permutations and greedy vehicle partitions.
- **Feasibility Repair & 2-Opt Search**: Automatic capacity constraint repair on candidate routes coupled with an intra-route 2-opt local search pass for path shortening.
- **Incident-Aware Selective Re-Routing**: Real-time road disruption modeling (`ACCIDENT`, `ROAD_CLOSURE`, `CONSTRUCTION`, `OBSTRUCTION`) with selective re-optimization of affected vehicles only.
- **Enterprise REST API**: Built with FastAPI, providing typed Pydantic v2 schemas, state dependency injection guards, and interactive OpenAPI documentation.
- **PostgreSQL Persistence Layer**: Relational persistence using SQLAlchemy 2.0, psycopg 3, and Alembic migrations for networks, fleets, optimization runs, convergence histories, and incidents.
- **Scientific Benchmarking Suite**: Comparative evaluation suite against Classical PSO, Genetic Algorithm (GA), Simulated Annealing (SA), and Branch-and-Bound Exact Solvers across standardized problem instances.
- **Modern Web Application**: Interactive dashboard built with React 19, Vite, Tailwind CSS, Recharts, and React-Leaflet across 7 dedicated operational views.

---

## 3. Technology Stack

| Layer | Technologies | Purpose |
|---|---|---|
| **Frontend** | React 19, Vite, Tailwind CSS, Recharts, React-Leaflet | Operational user interface, interactive maps, and convergence telemetry |
| **Backend API** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 | REST API routing, validation, and request lifecycle management |
| **Optimization Core** | NumPy, SciPy, Custom Discrete QPSO + 2-Opt | Stochastic quantum particle swarm optimization and local search |
| **Graph & Routing** | NetworkX | Directed transport graph modeling and Dijkstra shortest path finding |
| **Database & ORM** | PostgreSQL 18, SQLAlchemy 2.0, psycopg 3, Alembic | Relational data persistence, schema migrations, and connection pooling |
| **Benchmarking** | Pandas, Matplotlib, Custom Comparator Suite | Multi-algorithm evaluation, statistical analysis, and chart generation |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX | Automated unit, integration, and API regression testing |

---

## 4. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        React 19 Frontend (Vite)                        │
│   Dashboard · Network · Fleet · Optimization · Routes · Incidents · Analytics │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / JSON
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          FastAPI REST Boundary                         │
│       POST /network · POST /fleet · POST /optimize · POST /incidents    │
│            GET /routes/current · GET /analytics/convergence             │
└───────────────┬────────────────────────────────────────┬───────────────┘
                │                                        │
                ▼ In-Memory Execution                    ▼ Relational Persistence
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│       Core Application Stack         │  │     PostgreSQL Database      │
│  - TransportGraph (NetworkX)         │  │  - networks & nodes & edges   │
│  - Traffic & IncidentLayer           │  │  - fleet_vehicles & customers │
│  - VRPProblem & Feasibility Checker  │  │  - optimization_runs (JSONB) │
│  - QPSOOptimizer + Repair + 2-Opt    │  │  - routes & incidents         │
│  - RouteManager (Active Routes)      │  │  - Alembic Version Tracking   │
└──────────────────────────────────────┘  └──────────────────────────────┘
```

### Experimentation & Benchmarking Architecture
Separated from the production API boundary, the benchmarking engine evaluates algorithm performance systematically:
```
Instance Generator (Small/Medium/Large/Stress)
   │
   ▼
Unified Benchmark Runner (QPSO vs Classical PSO vs GA vs SA vs Exact)
   │
   ▼
Statistical Analysis Engine (Mean, Std, Min, Max, Optimality Gap, Runtime)
   │
   ▼
Scientific Visualizations (Convergence SVG, Runtime Scaling, Feasibility)
```

---

## 5. Optimization Architecture (QPSO Pipeline)

The discrete QPSO solver resolves combinatorial VRP instances through a continuous-to-discrete transformation:

```
1. Particle Initialization ──► Continuous position vectors X_i in [0, 1]^D
2. Permutation Decoding    ──► Sort-key ranking maps continuous coords to customer order
3. Vehicle Partitioning    ──► Split customer sequence into vehicle routes by capacity
4. Feasibility Repair      ──► Repair overloaded vehicles and ensure depot connectivity
5. Objective Evaluation    ──► Fitness = wT·TravelTime + wD·Distance + wC·Congestion
6. Quantum State Update    ──► Compute mbest attractor; update positions via wave function
7. 2-Opt Local Search      ──► Intra-route edge inversions refine the best feasible solution
```

The objective function evaluates multi-criteria trade-offs:
$$\text{Fitness} = w_T \cdot \text{TravelTime} + w_D \cdot \text{Distance} + w_C \cdot \text{CongestionPenalty} + \text{Penalty}_{\text{violations}}$$

All components import canonical weights (`w_time=1.0`, `w_distance=0.5`, `w_congestion=0.3`) to ensure strict consistency across the optimizer, API, and benchmark runners.

---

## 6. Database Architecture

Q-Route uses **PostgreSQL** for persistent storage, managed via **SQLAlchemy 2.0** declarative ORM models and **Alembic** migrations:

- **`networks`**: Network generation metadata, seed, node/edge counts, and active scenario status.
- **`nodes`**: Vertices with spatial coordinates ($x, y$) and roles (`depot`, `customer`, `intersection`).
- **`edges`**: Directed road segments, base travel time, congestion factor, and road status (`open`/`closed`).
- **`fleet_vehicles`**: Vehicle configurations, capacities, and home depot assignments.
- **`customers`**: Delivery orders, demands, and destination location node IDs.
- **`optimization_runs`**: QPSO hyper-parameters, fitness scores, repair breakdown, and full `convergence_history` stored as JSONB.
- **`routes`**: Generated vehicle routes with ordered stop sequences, ETA, metrics, and operational status.
- **`incidents`**: Road disruption registry tracking affected link coordinates, disruption type, and severity.

Database operations are abstracted into a repository/CRUD layer ([`backend/app/db/crud.py`](backend/app/db/crud.py)), ensuring database persistence remains cleanly decoupled from in-memory optimization execution.

---

## 7. Benchmarking & Scientific Evaluation

Q-Route includes a scientific evaluation framework comparing QPSO against conventional algorithms on identical problem instances:

### 1. Comparator Suite
- **Classical PSO**: Velocity-clamped continuous particle swarm with sort-key decoding.
- **Genetic Algorithm (GA)**: Order-crossover (OX), swap mutation, and elitist survival.
- **Simulated Annealing (SA)**: Temperature-cooled 2-opt and swap neighborhood exploration.
- **Exact Solver**: Optimal brute-force baseline for small instances ($N \le 8$).

### 2. Standardized Instances
- 20 controlled benchmark instances across 4 size tiers:
  - **Small** ($N=6$ nodes, 1 depot, 4 customers)
  - **Medium** ($N=15$ nodes, 1 depot, 8 customers)
  - **Large** ($N=30$ nodes, 2 depots, 16 customers)
  - **Stress** ($N=50$ nodes, 3 depots, 28 customers)

### 3. Empirical Results & Artifacts
- **Global Optimality Proved**: On small instances, QPSO consistently converged to the exact theoretical global optimum discovered by the Exact Solver ($78.6381$ fitness, $0.0\%$ gap) in $\approx 3.3\text{s}$, compared to $\approx 91.6\text{s}$ for the brute-force solver.
- **Visualizations**: Generated in [`results/figures/`](results/figures/):
  - `convergence_comparison.svg`: Iteration-by-iteration fitness curves.
  - `runtime_comparison.svg`: Wall-clock execution time across algorithms.
  - `scalability_runtime.svg`: Runtime scaling curve ($O(N)$ vs $O(N!)$).
  - `scalability_objective.svg`: Solution quality scaling across problem sizes.

---

## 8. Project Evolution & Milestones

| Milestone | Scope / Deliverable | Status |
|---|---|---|
| **M1** | Core Transport Graph engine, NetworkX model, and shortest-path pathfinding | **Completed** |
| **M2** | Synthetic road network generator with spatial Euclidean layout | **Completed** |
| **M3** | Traffic simulation layer, speed limits, and congestion multipliers | **Completed** |
| **M4** | Multi-Vehicle VRP formulation, feasibility checker, and multi-objective function | **Completed** |
| **M5** | Discrete Quantum PSO (QPSO) metaheuristic solver implementation | **Completed** |
| **M6** | Solution feasibility repair algorithm and 2-opt local search refinement | **Completed** |
| **M7** | Road disruption modeling, incident severity, and affected route detection | **Completed** |
| **M8** | Active route lifecycle manager, validation, and ETA calculation | **Completed** |
| **M9** | FastAPI REST API layer, state management, and endpoint contracts | **Completed** |
| **M10** | Enterprise React frontend (7 pages: Dashboard, Network, Fleet, Opt, Routes, Incidents, Analytics) | **Completed** |
| **M11 Phase 1** | Comparator algorithms suite (Classical PSO, GA, SA, Exact solver) | **Completed** |
| **M11 Phase 2** | Standardized benchmark instance suite (20 instances across 4 size tiers) | **Completed** |
| **M11 Phase 3** | Unified benchmark runner with multi-seed trials and JSON/CSV export | **Completed** |
| **M11 Phase 4** | Statistical analysis engine, metrics aggregation, and vector SVG visualizations | **Completed** |
| **M11 Database** | PostgreSQL 18 persistence architecture, SQLAlchemy models, Alembic, and API CRUD | **Completed** |
| **M12** | Dynamic incident rerouting evaluation, simulation, and operational benchmark | **In Progress** |

---

## 9. Testing & Verification

Q-Route maintains automated test coverage across all domain layers:

- **Total Backend Tests**: **385 passing tests** across 15 test modules.
- **Execution Time**: $\approx 39.4\text{s}$ full suite run.
- **Coverage Areas**:
  - Graph algorithms and Dijkstra pathfinding
  - Traffic and speed reduction mechanics
  - VRP constraints and capacity validation
  - QPSO optimizer convergence and 2-opt refinement
  - Incident layer and affected-route isolation
  - RouteManager lifecycle and ETA tracking
  - FastAPI endpoints and status code contracts (200, 400, 409, 422)
  - Database connectivity, model CRUD, cascade deletions, and API persistence
  - Comparator algorithms, instance generator, and statistical analysis
- **Frontend Verification**: Production build (`vite build`) compiles cleanly with 0 errors.

---

## 10. Project Structure

```
Q-Route/
├── backend/
│   ├── alembic/                  # Alembic database migration environment
│   │   ├── versions/             # Migration revision scripts (001_initial_schema.py)
│   │   └── env.py                # Migration runner script
│   ├── app/
│   │   ├── api/                  # FastAPI REST routing layer
│   │   │   ├── routes/           # Endpoints: network, fleet, optimize, incidents, etc.
│   │   │   ├── dependencies.py   # State & database dependency injection
│   │   │   ├── models.py         # Pydantic v2 request/response schemas
│   │   │   └── state.py          # In-memory application state container
│   │   ├── core/                 # App configuration & pydantic-settings
│   │   ├── db/                   # Database session, base model, models & CRUD helpers
│   │   ├── graph/                # TransportGraph & synthetic generator
│   │   ├── incidents/            # IncidentLayer & disruption models
│   │   ├── qpso/                 # QPSO optimizer, particle, repair, 2-opt
│   │   ├── routes/               # RouteManager, ActiveRoute, ETA validation
│   │   ├── traffic/              # TrafficLayer & congestion states
│   │   ├── vrp/                  # VRPProblem, Customer, Vehicle, objective, feasibility
│   │   └── main.py               # FastAPI application entry point
│   ├── tests/                    # 15 test suites (385 tests)
│   ├── alembic.ini               # Alembic configuration
│   └── requirements.txt          # Python dependencies
├── frontend/                     # React 19 + Vite application
│   ├── src/
│   │   ├── components/           # UI components (forms, tables, canvas, charts)
│   │   ├── pages/                # 7 views: Dashboard, Network, Fleet, Opt, Routes, Incidents, Analytics
│   │   ├── services/             # API client services
│   │   └── index.css             # Design tokens & styling
│   └── package.json
├── data/                         # Datasets & standardized benchmark instances
│   └── benchmarks/               # 20 benchmark JSON instances (Small, Medium, Large, Stress)
├── experiments/                  # Standalone experiment & benchmark scripts
│   ├── benchmarks/               # Benchmark runner, adapters, analysis & plotting
│   ├── comparators/              # Classical PSO, GA, SA, Exact solver
│   └── run_qpso.py               # Interactive CLI experiment runner
├── results/                      # Experiment logs & generated artifacts
│   ├── analysis/                 # Summary CSV and Markdown statistical reports
│   ├── benchmarks/               # Raw experiment JSON/CSV run data
│   └── figures/                  # Vector SVG publication-quality figures
├── docs/                         # Detailed technical documentation
│   ├── API.md                    # REST API specifications and example payloads
│   ├── M10_NOTES.md              # Frontend architecture and UI component documentation
│   └── M11_AUDIT.md              # Scientific benchmarking & database audit report
└── README.md
```

---

## 11. Documentation Index

Detailed architectural records and API specifications are maintained in the [`docs/`](docs/) directory:

- **[API Documentation](docs/API.md)**: Detailed specification of all REST endpoints, request/response models, and call ordering rules.
- **[Frontend Architecture (M10 Notes)](docs/M10_NOTES.md)**: Frontend design system, component hierarchy, and page specifications.
- **[Benchmarking & Database Audit (M11 Audit)](docs/M11_AUDIT.md)**: Comprehensive evaluation results, exact solver proofs, algorithm comparison matrices, and PostgreSQL architecture details.

---

## 12. How to Run Locally

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL 18+ (running locally)

### 1. Database Setup
1. Ensure PostgreSQL is running on `localhost:5432` with a database named `qroute`.
2. Configure credentials by copying the environment template:
   ```bash
   cp backend/.env.example backend/.env
   ```
3. Update `DATABASE_URL` in `backend/.env` with your PostgreSQL user and password:
   ```text
   DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/qroute
   ```

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API Base URL: **http://localhost:8000**
- Interactive Swagger UI: **http://localhost:8000/docs**
- Health Check: **http://localhost:8000/health**

### 3. Frontend Setup
```bash
# In a new terminal, navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

- Frontend App URL: **http://localhost:5173**

### 4. Running Benchmarks
```bash
# Run the unified benchmark sweep across all algorithms and instances
python -m experiments.benchmarks.run_benchmark --trials 5

# Generate statistical reports and visualizations
python -m experiments.benchmarks.analyze_results
```

---

## 13. Current Status

- **M11 Complete & Verified**: Comparator algorithms, standardized instances, unified benchmark runner, statistical analysis, and PostgreSQL persistence architecture are completed, tested (385 passing tests), and committed to `main`.
- **M12 Active**: Dynamic incident rerouting evaluation and simulation benchmark is currently beginning.

---

## 14. Future Work

- **Dynamic Incident Benchmark Suite (M12)**: Systematic evaluation of selective vehicle re-optimization versus full fleet re-solve under varying road disruption loads.
- **OpenStreetMap (OSM) & GIS Ingestion**: Real-world road network importing and address geocoding support.
- **Multi-Depot VRP with Time Windows (MDVRPTW)**: Extended formulation supporting distributed depots and delivery appointment windows.

---

## 15. License

To be decided.
