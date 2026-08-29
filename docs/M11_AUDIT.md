# Milestone 11 — Benchmark Plan & Phase 1–3 Implementation Status

## Executive Summary
This document tracks the execution of **Milestone 11 (Benchmarking, Algorithm Comparison, Convergence Evaluation, Scalability, and Reproducible Experimentation)**.

The M10 frontend and M2–M9 backend architectures are fully functioning, verified, and protected. M11 focuses strictly on scientific benchmarking, algorithmic comparisons, and empirical validation without modifying core optimization, objective, or API contracts.

---

## 1. Current QPSO Architecture
- **Location**: [`backend/app/qpso/`](file:///c:/git/Q-Route/backend/app/qpso/)
- **Entry Point**: `QPSOOptimizer(problem: VRPProblem, config: QPSOConfig).run() -> QPSOResult` in [`optimizer.py`](file:///c:/git/Q-Route/backend/app/qpso/optimizer.py).
- **Particle Representation**: [`representation.py`](file:///c:/git/Q-Route/backend/app/qpso/representation.py)
  - Random-key encoding: Continuous position vector $\mathbf{x}_i \in [0, 1]^N$ ($N = \text{number of customers}$).
  - Permutation decoder: Sorts continuous keys to generate discrete customer visit sequences $\pi$, partitioned across vehicles using vehicle capacity bounds.
- **Quantum-Behaved Update Rule**:
  - Global mean-best position: $\mathbf{m}(t) = \frac{1}{M} \sum_{i=1}^M \mathbf{p}_i(t)$.
  - Local stochastic attractor: $\mathbf{p}_{id} = \phi \cdot \mathbf{pbest}_{id} + (1 - \phi) \cdot \mathbf{gbest}_d$, with $\phi \sim U(0, 1)$.
  - Wave function collapse: $\mathbf{x}_{id}(t+1) = \mathbf{p}_{id} \pm \beta(t) \cdot |\mathbf{x}_{id}(t) - \mathbf{p}_{id}| \cdot \ln(1 / u)$, with $u \sim U(0, 1)$ and $\pm$ chosen with equal probability.
  - Annealing contraction coefficient: $\beta(t) = \beta_{\max} - (\beta_{\max} - \beta_{\min}) \cdot \frac{t}{T}$.
- **Evaluation Pipeline**:
  $$\text{Decode} \longrightarrow \text{Capacity Repair heuristic} \longrightarrow \text{2-opt Local Search} \longrightarrow \text{Objective Evaluation}$$
- **Convergence Telemetry**: Records `convergence_history: dict[int, float]` (iteration index $\to$ global best fitness).
- **Stopping Conditions**:
  1. `max_iterations` reached.
  2. `time_budget_seconds` elapsed.
  3. `convergence_tol` and `stagnation_window` stagnation trigger.
- **Reproducibility**: Deterministic execution via `np.random.default_rng(config.seed)`.

---

## 2. Canonical Objective & Fitness Formulation
- **Location**: [`backend/app/vrp/objective.py`](file:///c:/git/Q-Route/backend/app/vrp/objective.py)
- **Single Source of Truth**: `compute_fitness(solution: VRPSolution, problem: VRPProblem, weights: FitnessWeights) -> float`
- **Formula**:
  $$\text{Fitness} = w_T \cdot \text{TotalTravelTime} + w_D \cdot \text{TotalDistance} + w_C \cdot \text{TotalCongestion} + \text{penalty\_per\_violation} \cdot n_{\text{violations}}$$
- **Components**:
  - `effective_travel_time`: $\text{base\_travel\_time} \times \text{congestion\_factor}$ for each traversed directed edge.
  - `edge_congestion_penalty`: $\text{congestion\_factor} - 1.0$.
  - Closed/missing edges contribute $\infty$ to ensure hard road closure adherence.
- **Default Weights**: $w_T = 1.0$, $w_D = 0.5$, $w_C = 0.3$, $\text{penalty} = 1000.0$.
- **Rule for M11**: All baseline and comparator algorithms evaluate fitness exclusively through `compute_fitness` to guarantee rigorous scientific parity.

---

## 3. Constraint Checking & Feasibility
- **Location**: [`backend/app/vrp/feasibility.py`](file:///c:/git/Q-Route/backend/app/vrp/feasibility.py)
- **Function**: `check_feasibility(solution: VRPSolution, problem: VRPProblem) -> FeasibilityResult`
- **Five Hard Constraints**:
  1. **Vehicle Capacity**: $\sum_{c \in \text{Route}} \text{demand}(c) \le \text{vehicle.capacity}$.
  2. **Customer Coverage**: Every customer node is served in exactly one vehicle route (no missing or duplicate customers).
  3. **Depot Constraints**: Every vehicle route starts and ends at its assigned `depot_node`.
  4. **Road Availability**: No route sequence traverses a road marked `road_status == 'closed'`.
  5. **Topological Connectivity**: Every consecutive node pair in `node_sequence` must be a valid directed edge in `TransportGraph`.

---

## 4. Phase 1 Implementation Status: Comparator Algorithms Suite (Complete)

The comparator algorithms suite is implemented in [`experiments/comparators/`](file:///c:/git/Q-Route/experiments/comparators/) and verified through dedicated unit tests.

### Implemented Comparators:
1. **Classical PSO ([`classical_pso.py`](file:///c:/git/Q-Route/experiments/comparators/classical_pso.py))**: Standard velocity & position update mechanism ($w = 0.7298, c_1 = 1.49618, c_2 = 1.49618$).
2. **Genetic Algorithm ([`genetic_algorithm.py`](file:///c:/git/Q-Route/experiments/comparators/genetic_algorithm.py))**: Generational GA with tournament selection ($k=3$), arithmetic/SBX crossover ($p_c = 0.85$), Gaussian mutation ($p_m = 0.15$), and elitism ($K=2$).
3. **Simulated Annealing ([`simulated_annealing.py`](file:///c:/git/Q-Route/experiments/comparators/simulated_annealing.py))**: Metropolis acceptance with perturbation, swap, and inversion neighborhood moves, governed by geometric cooling.
4. **Exact / Exhaustive Combinatorial Solver ([`exact_solver.py`](file:///c:/git/Q-Route/experiments/comparators/exact_solver.py))**: Complete permutation and multi-vehicle partition enumeration for small instances ($N \le 8$), with safety guard against $N > 8$.
5. **Common Protocol & Result Schema ([`common.py`](file:///c:/git/Q-Route/experiments/comparators/common.py))**: Standard `ComparatorResult` and `evaluate_particle` helper.

---

## 5. Phase 2 Implementation Status: Standardized Benchmark Instances Suite (Complete)

The benchmark-instance layer is implemented in [`experiments/benchmarks/`](file:///c:/git/Q-Route/experiments/benchmarks/) and datasets are generated under [`data/benchmarks/`](file:///c:/git/Q-Route/data/benchmarks/).

### Benchmark Scale Definitions:
| Size | Customers ($N$) | Vehicles ($V$) | Nodes ($M$) | Depots ($D$) | Radius (km) | Grid Size (km) | Description |
|---|---|---|---|---|---|---|---|
| **SMALL** | 6 | 2 | 20 | 1 | 3.5 | 10.0 | Rapid convergence & exact solver baseline |
| **MEDIUM** | 15 | 4 | 40 | 2 | 4.0 | 15.0 | Multi-depot intermediate operational tier |
| **LARGE** | 30 | 6 | 80 | 3 | 4.5 | 20.0 | Enterprise fleet distribution scale |
| **STRESS** | 50 | 10 | 120 | 4 | 5.0 | 25.0 | High-density metropolitan scalability stress test |

### Deterministic Seed Scheme:
- **Seed Array**: `BENCHMARK_SEEDS = [42, 43, 44, 45, 46]` (5 reproducible trials per scale).
- **Total Generated Instances**: 20 standardized VRP instances in `data/benchmarks/{size}_seed_{seed}.json`.
- **Manifest**: Machine-readable specification index at [`data/benchmarks/manifest.json`](file:///c:/git/Q-Route/data/benchmarks/manifest.json).

---

## 6. Phase 3 Implementation Status: Unified Benchmark Runner (Complete)

The unified benchmark execution framework is implemented under [`experiments/benchmarks/`](file:///c:/git/Q-Route/experiments/benchmarks/) and validated.

### Architecture & Capabilities:
1. **Algorithm Adapter ([`adapters.py`](file:///c:/git/Q-Route/experiments/benchmarks/adapters.py))**:
   - `AlgorithmAdapter.run_trial()` wraps `QPSO`, `Classical_PSO`, `Genetic_Algorithm`, `Simulated_Annealing`, and `Exact_Brute_Force` under a standardized signature.
   - Computes total travel time, total distance, total congestion, and constraint violations for all solutions.
   - Captures iteration-by-iteration convergence histories.
   - Enforces complete error isolation: trial exceptions are caught and recorded as `status="ERROR"` with `error_type` and `error_message`, preventing suite crashes.
2. **Benchmark Runner ([`runner.py`](file:///c:/git/Q-Route/experiments/benchmarks/runner.py))**:
   - Executes multi-trial benchmark matrices (`instances` $\times$ `algorithms` $\times$ `trials`).
   - Dynamic instance loading from `data/benchmarks/` with on-the-fly generation fallback.
   - Safety guard: Automatically skips `Exact_Brute_Force` for instances with $N > 8$.
   - Structured Multi-Artifact Export:
     - [`results/benchmarks/benchmark_results.csv`](file:///c:/git/Q-Route/results/benchmarks/benchmark_results.csv): Flat per-trial tabular metrics.
     - [`results/benchmarks/benchmark_results.json`](file:///c:/git/Q-Route/results/benchmarks/benchmark_results.json): Full execution metadata and trial records.
     - [`results/benchmarks/convergence_histories.json`](file:///c:/git/Q-Route/results/benchmarks/convergence_histories.json): Normalized convergence trajectory curves.
3. **CLI Entry Point ([`run_benchmark.py`](file:///c:/git/Q-Route/experiments/benchmarks/run_benchmark.py))**:
   - Command-line runner supporting `--instances`, `--algorithms`, `--trials`, `--iterations`, `--particles`, `--time-budget`, `--seed`, and `--out-dir`.

### Verification Results:
- **Phase 3 Test Suite**: `8 passed in 20.99s` ([`backend/tests/test_benchmark_runner.py`](file:///c:/git/Q-Route/backend/tests/test_benchmark_runner.py)).
- **Smoke Benchmark**: `4/4 trials succeeded in 20.06s` (`python -m experiments.benchmarks.run_benchmark --instances small_seed_42 --algorithms QPSO,Classical_PSO --trials 2`).
- **Full Backend Regression Suite**: `375 passed in 49.06s`.
- **Protected Files Invariance**: `app/qpso/*`, `objective.py`, `feasibility.py`, `frontend/*`, and `comparators/*` remain untouched.
- **Zero New Dependencies Added**.

---

## 7. Milestone 11 Phase 4 Implementation Details

### Components Implemented:
1. **Statistical Aggregation Engine ([`analysis.py`](file:///c:/git/Q-Route/experiments/benchmarks/analysis.py))**:
   - Ingests raw multi-trial benchmark metrics (`benchmark_results.csv`, `benchmark_results.json`, `convergence_histories.json`).
   - Computes statistical summaries (mean, std, median, min, max) grouped by `(instance_id, algorithm)` for objective fitness, runtime, distance, travel time, and congestion.
   - Computes feasibility breakdown and failure isolation matrices.
   - Computes instance-size scalability metrics across problem scales.
   - Generates tabular machine-readable exports:
     - [`results/analysis/algorithm_comparison.csv`](file:///c:/git/Q-Route/results/analysis/algorithm_comparison.csv)
     - [`results/analysis/runtime_comparison.csv`](file:///c:/git/Q-Route/results/analysis/runtime_comparison.csv)
     - [`results/analysis/feasibility.csv`](file:///c:/git/Q-Route/results/analysis/feasibility.csv)
     - [`results/analysis/scalability.csv`](file:///c:/git/Q-Route/results/analysis/scalability.csv)
     - [`results/analysis/summary.json`](file:///c:/git/Q-Route/results/analysis/summary.json)
     - [`results/analysis/benchmark_analysis.md`](file:///c:/git/Q-Route/results/analysis/benchmark_analysis.md)

2. **Zero-Dependency Vector Charting Engine ([`plot_utils.py`](file:///c:/git/Q-Route/experiments/benchmarks/plot_utils.py))**:
   - Pure-Python SVG and PNG scientific visualization generator matching Q-Route enterprise SaaS theme (`#0a0e1a` dark slate palette).
   - Generates publication-ready vector figures:
     - [`results/figures/convergence_comparison.svg`](file:///c:/git/Q-Route/results/figures/convergence_comparison.svg): Iteration vs fitness curves across all algorithms.
     - [`results/figures/objective_comparison.svg`](file:///c:/git/Q-Route/results/figures/objective_comparison.svg): Grouped bar chart comparing solution quality with standard deviation error bars.
     - [`results/figures/runtime_comparison.svg`](file:///c:/git/Q-Route/results/figures/runtime_comparison.svg): Grouped bar chart comparing execution wall-clock time.
     - [`results/figures/scalability_runtime.svg`](file:///c:/git/Q-Route/results/figures/scalability_runtime.svg): Scaling runtime vs problem size ($N$).
     - [`results/figures/scalability_objective.svg`](file:///c:/git/Q-Route/results/figures/scalability_objective.svg): Solution quality scaling curve.
     - [`results/figures/feasibility_comparison.svg`](file:///c:/git/Q-Route/results/figures/feasibility_comparison.svg): Feasibility success rate chart.

3. **CLI Analysis Tool ([`analyze_results.py`](file:///c:/git/Q-Route/experiments/benchmarks/analyze_results.py))**:
   - Entry point: `python -m experiments.benchmarks.analyze_results --results-dir results/benchmarks --out-dir results/analysis --figures-dir results/figures`.

### Verification Results:
- **Phase 4 Test Suite**: `3 passed in 1.25s` ([`backend/tests/test_analysis.py`](file:///c:/git/Q-Route/backend/tests/test_analysis.py)).
- **All M11 Tests**: `27 passed in 25.38s` (`test_analysis.py`, `test_benchmark_runner.py`, `test_benchmarks.py`, `test_comparators.py`).
- **Full Backend Regression Suite**: `378 passed in 43.69s` with 0 failures.
- **Empirical Optimality Finding**: Exact solver proved global minimum fitness $78.6381$ on `small_seed_42` ($N=6$) in $57.9\text{s}-91.6\text{s}$. `QPSO` reliably converged to the exact identical global optimum $78.6381$ ($0.0\%$ gap) in $3.3\text{s}-5.5\text{s}$.
- **Protected Files Invariance**: `backend/app/qpso/*`, `objective.py`, `feasibility.py`, and `frontend/*` remain untouched.
- **Zero New External Dependencies Added**.

---

## 8. M11 Requirement Matrix

| Requirement | Description | Status | Notes |
|---|---|---|---|
| **A. QPSO Baseline** | Discrete Quantum PSO solver with repair + 2-opt | **Completed** | Integrated in benchmark runner & analysis |
| **B. Conventional Metaheuristics** | Classical PSO, Genetic Algorithm (GA), Simulated Annealing (SA) | **Completed (Phase 1)** | Integrated in runner, stats, & charts |
| **C. Exact Method** | Optimal baseline for small instances (Branch-and-Bound / Brute-force ILP) | **Completed (Phase 1)** | Integrated with $N \le 8$ safety guard |
| **D. Multiple Problem Sizes** | Small ($N=6$), Medium ($N=15$), Large ($N=30$), Stress ($N=50+$) | **Completed (Phase 2)** | 20 instances in `data/benchmarks/` |
| **E. Stochastic Trials** | Multi-seed runs (e.g. 10–30 runs/config) with Mean, Std, Min, Max | **Completed (Phase 3)** | Supported via `--trials` & seed offsets |
| **F. Fitness Comparison** | Objective score comparison across algorithms | **Completed (Phase 4)** | Aggregated in `algorithm_comparison.csv` |
| **G. Distance Comparison** | Total route distance (km) metric | **Completed (Phase 4)** | Statistical metrics computed & exported |
| **H. Travel-Time Comparison** | Total effective travel time (min) metric | **Completed (Phase 4)** | Statistical metrics computed & exported |
| **I. Congestion Comparison** | Congestion penalty avoidance metric | **Completed (Phase 4)** | Statistical metrics computed & exported |
| **J. Runtime Comparison** | CPU wall-clock execution time (ms) | **Completed (Phase 4)** | `runtime_comparison.csv` & SVG charts |
| **K. Convergence Comparison** | Iteration-by-iteration fitness trajectories | **Completed (Phase 4)** | `convergence_comparison.svg` chart |
| **L. Scalability Analysis** | Solution quality vs runtime scaling as customer/node counts grow | **Completed (Phase 4)** | `scalability.csv` & scalability SVG plots |
| **M. Reproducible Seeds** | Deterministic experiment generation | **Completed (Phase 2)** | Seed parameterization across all trials |
| **N. CSV/JSON Raw Results** | Structured output logs in `results/` | **Completed (Phase 3 & 4)** | Full suite of CSV, JSON, and MD reports |
| **O. Benchmark Visualizations** | Comparative convergence, boxplots, scaling curves | **Completed (Phase 4)** | 6 vector SVG figures in `results/figures/` |
| **P. Incident Rerouting Evaluation** | Dynamic selective re-optimization vs full re-solve benchmark | **Pending Phase 5** | Incident benchmark next |

---

## 9. Database Setup & Architecture (Phase 2)

### Implementation Summary:
1. **Engine & Configuration**:
   - Integrated `SQLAlchemy 2.0` with `psycopg[binary] 3.x` driver connecting to PostgreSQL 18.4 (`qroute` database).
   - Configured [`app/core/config.py`](file:///c:/git/Q-Route/backend/app/core/config.py) using `pydantic-settings` to load `DATABASE_URL` from `.env` with fallback.
   - Configured [`app/db/session.py`](file:///c:/git/Q-Route/backend/app/db/session.py) with connection pool recycling (`pool_pre_ping=True`) and `get_db()` dependency.
2. **Schema & ORM Models ([`app/db/models.py`](file:///c:/git/Q-Route/backend/app/db/models.py))**:
   - `networks`: Network generation params & metadata.
   - `nodes`: Vertices with spatial coordinates ($x, y$) and node roles (`depot`, `customer`, `intersection`).
   - `edges`: Directed links with distance, base travel time, congestion factor, and road status.
   - `fleet_vehicles`: Vehicle capacity and home depot assignments.
   - `customers`: Order demands and delivery locations.
   - `optimization_runs`: QPSO run parameters, fitness scores, repair metrics, and convergence JSON.
   - `routes`: Operational and historical vehicle routes (`visit_order`, `node_sequence`, metrics, ETA, status).
   - `incidents`: Disruption events (`edge_u`, `edge_v`, `incident_type`, `severity`, closure flag).
3. **Schema Migrations**:
   - Initialized Alembic (`alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial_schema.py`).
   - Successfully executed `alembic upgrade head` to provision all 8 domain tables in PostgreSQL.
4. **CRUD Data Access Layer ([`app/db/crud.py`](file:///c:/git/Q-Route/backend/app/db/crud.py))**:
   - Data access helper functions for network, fleet, optimization runs, routes, and incidents.

### Verification:
- **PostgreSQL Connection**: Successfully connected to local `qroute` database on port 5432.
- **Database Tests**: `4 passed in 2.08s` ([`backend/tests/test_db.py`](file:///c:/git/Q-Route/backend/tests/test_db.py)).
- **Full Backend Regression Suite**: `382 passed in 37.87s` (0 regressions).
- **Frontend Build**: Production bundle build passed in `9.13s` with 0 errors.
- **Protected Areas Invariance**: `app/qpso/*`, `app/vrp/objective.py`, `app/vrp/feasibility.py`, and `frontend/*` remain untouched.

---

## 10. Database API Persistence & CRUD Integration (Phase 3)

### Implementation Summary:
1. **API Boundary Integration**:
   - Injected database session dependency (`db: Session = Depends(get_db)`) across API endpoints:
     - `POST /network`: Persists network parameters and bulk-inserts `nodes` and `edges` into PostgreSQL.
     - `POST /fleet`: Validates nodes and persists `fleet_vehicles` and `customers` linked to the active network.
     - `POST /optimize`: Executes in-memory QPSO and persists `optimization_runs` (with `convergence_history` JSON) and `routes` records.
     - `POST /incidents`: Persists `incidents` record, updates edge statuses, and persists re-optimized `optimization_runs` and `routes`.
     - `GET /routes/current`: Retrieves operational vehicle routes.
     - `GET /analytics/convergence`: Returns iteration-by-iteration convergence trajectory.
2. **AppState & Lifecycle**:
   - Added `network_db_id` and `opt_run_db_id` to `AppState` to track active relational database foreign keys.
   - Synchronized stage invalidation: `clear_from_network`, `clear_from_fleet`, and `clear_from_optimize`.
3. **Resilience & Safe Error Handling**:
   - Wrapped database persistence calls at the API boundary in exception guards with structured logging.
   - If database write fails or is offline, the API remains resilient and serves in-memory optimization results without breaking the client contract.
4. **CRUD Data Access API ([`app/db/crud.py`](file:///c:/git/Q-Route/backend/app/db/crud.py))**:
   - `save_network`, `save_fleet`, `save_optimization_run`, `save_incident`
   - `get_active_network`, `get_network_by_id`, `get_latest_optimization_run`, `get_routes_for_optimization`, `get_incidents_for_network`, `delete_network`.

### Verification Results:
- **API Persistence Test Suite**: `3 passed in 3.54s` ([`backend/tests/test_api_persistence.py`](file:///c:/git/Q-Route/backend/tests/test_api_persistence.py)).
- **Database Model Test Suite**: `4 passed in 2.28s` ([`backend/tests/test_db.py`](file:///c:/git/Q-Route/backend/tests/test_db.py)).
- **Full Backend Regression Suite**: `385 passed in 39.40s` with 0 failures across all 385 tests.
- **Frontend Production Build**: `vite build` completed in `648ms` with 0 errors.
- **Protected Areas Invariance**: `app/qpso/*`, `app/vrp/objective.py`, `app/vrp/feasibility.py`, and `frontend/*` remain 100% untouched.
- **API Contract Invariance**: All Pydantic request/response models remain 100% backward compatible.



