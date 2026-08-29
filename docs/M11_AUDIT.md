# Milestone 11 — Benchmark Plan & Phase 1 Implementation Status

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

The comparator algorithms suite has been implemented in [`experiments/comparators/`](file:///c:/git/Q-Route/experiments/comparators/) and verified through dedicated unit tests.

### Implemented Comparators:
1. **Classical PSO ([`classical_pso.py`](file:///c:/git/Q-Route/experiments/comparators/classical_pso.py))**:
   - Standard velocity & position update mechanism with inertia weight ($w = 0.7298$) and acceleration coefficients ($c_1 = 1.49618, c_2 = 1.49618$).
   - Reuses priority-key encoding and canonical decoding pipeline.
2. **Genetic Algorithm ([`genetic_algorithm.py`](file:///c:/git/Q-Route/experiments/comparators/genetic_algorithm.py))**:
   - Generational GA with tournament selection ($k=3$), arithmetic/SBX crossover ($p_c = 0.85$), Gaussian mutation ($p_m = 0.15$), and elitism ($K=2$).
3. **Simulated Annealing ([`simulated_annealing.py`](file:///c:/git/Q-Route/experiments/comparators/simulated_annealing.py))**:
   - Metropolis acceptance criterion with perturbation, customer-swap, and inversion neighborhood moves, governed by geometric cooling ($T_{k+1} = \alpha T_k$).
4. **Exact / Exhaustive Combinatorial Solver ([`exact_solver.py`](file:///c:/git/Q-Route/experiments/comparators/exact_solver.py))**:
   - Complete permutation and multi-vehicle partition enumeration for small instances ($N \le 8$).
   - Safety guard: Explicitly raises `ValueError` if $N > 8$ to prevent combinatorial explosion.
5. **Common Protocol & Result Schema ([`common.py`](file:///c:/git/Q-Route/experiments/comparators/common.py))**:
   - `ComparatorResult` exposing `algorithm_name`, `best_solution`, `best_fitness`, `convergence_history`, `runtime_seconds`, `is_feasible`, `seed`, `iterations_completed`.
   - `evaluate_particle` helper ensuring identical decoding, capacity repair, 2-opt, and fitness scoring.

### Verification Results:
- **Dedicated Comparator Tests**: `8 passed in 5.82s` ([`backend/tests/test_comparators.py`](file:///c:/git/Q-Route/backend/tests/test_comparators.py)).
- **Full Backend Regression Suite**: `359 passed in 21.85s`.
- **Zero Modifications**: `app/qpso/*`, `objective.py`, `feasibility.py`, and `frontend/*` remain completely untouched.
- **Zero New Dependencies Added**.

---

## 5. M11 Requirement Matrix

| Requirement | Description | Status | Notes |
|---|---|---|---|
| **A. QPSO Baseline** | Discrete Quantum PSO solver with repair + 2-opt | **Already Exists** | Fully implemented in `app.qpso.optimizer` |
| **B. Conventional Metaheuristics** | Classical PSO, Genetic Algorithm (GA), Simulated Annealing (SA) | **Completed (Phase 1)** | Implemented in `experiments/comparators/` |
| **C. Exact Method** | Optimal baseline for small instances (Branch-and-Bound / Brute-force ILP) | **Completed (Phase 1)** | Implemented in `experiments/comparators/exact_solver.py` |
| **D. Multiple Problem Sizes** | Small ($N=6$), Medium ($N=15$), Large ($N=30$), Stress ($N=50+$) | **Pending Phase 2** | Standardized benchmark instance sets needed |
| **E. Stochastic Trials** | Multi-seed runs (e.g. 10–30 runs/config) with Mean, Std, Min, Max | **Pending Phase 3** | Benchmark runner required |
| **F. Fitness Comparison** | Objective score comparison across algorithms | **Pending Phase 3** | Raw CSV & statistical summary needed |
| **G. Distance Comparison** | Total route distance (km) metric | **Pending Phase 3** | Metric extraction required |
| **H. Travel-Time Comparison** | Total effective travel time (min) metric | **Pending Phase 3** | Metric extraction required |
| **I. Congestion Comparison** | Congestion penalty avoidance metric | **Pending Phase 3** | Metric extraction required |
| **J. Runtime Comparison** | CPU wall-clock execution time (ms) | **Pending Phase 3** | High-resolution timing needed |
| **K. Convergence Comparison** | Iteration-by-iteration fitness trajectories | **Pending Phase 4** | Trajectory plotting needed |
| **L. Scalability Analysis** | Solution quality vs runtime scaling as customer/node counts grow | **Pending Phase 4** | Scaling experiment suite needed |
| **M. Reproducible Seeds** | Deterministic experiment generation | **Completed (Phase 1)** | Deterministic seeded RNG across all comparators |
| **N. CSV/JSON Raw Results** | Structured output logs in `results/` | **Pending Phase 4** | Data export pipeline needed |
| **O. Benchmark Visualizations** | Comparative convergence, boxplots, scaling curves | **Pending Phase 4** | Plot generation script needed |
| **P. Incident Rerouting Evaluation** | Dynamic selective re-optimization vs full re-solve benchmark | **Pending Phase 5** | Incident benchmark needed |
