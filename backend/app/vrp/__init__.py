"""
app/vrp/__init__.py – Public API for the Q-Route VRP package.

Import from here rather than sub-modules directly:

    from app.vrp import Vehicle, Customer, VRPProblem
    from app.vrp import VehicleRoute, VRPSolution
    from app.vrp import check_feasibility, FeasibilityResult
    from app.vrp import compute_fitness, FitnessWeights, route_components
    from app.vrp import generate_vrp_instance, save_vrp_json, load_vrp_json
"""

from .models import Vehicle, Customer, VRPProblem, VehicleRoute, VRPSolution
from .feasibility import check_feasibility, FeasibilityResult
from .objective import compute_fitness, FitnessWeights, route_components
from .generator import (
    generate_vrp_instance,
    save_vrp_json,
    load_vrp_json,
    vrp_problem_to_dict,
    vrp_problem_from_dict,
    map_customer_location,
    map_depot_location,
    map_customer_locations,
    create_geographic_customer,
    create_geographic_vehicle,
    create_geographic_customers,
    create_geographic_vehicles,
    build_geographic_vrp_problem,
)

__all__ = [
    # Models
    "Vehicle",
    "Customer",
    "VRPProblem",
    "VehicleRoute",
    "VRPSolution",
    # Feasibility
    "check_feasibility",
    "FeasibilityResult",
    # Objective
    "compute_fitness",
    "FitnessWeights",
    "route_components",
    # Generator
    "generate_vrp_instance",
    "save_vrp_json",
    "load_vrp_json",
    "vrp_problem_to_dict",
    "vrp_problem_from_dict",
    # Geographic VRP Helpers (Milestone 13.5)
    "map_customer_location",
    "map_depot_location",
    "map_customer_locations",
    "create_geographic_customer",
    "create_geographic_vehicle",
    "create_geographic_customers",
    "create_geographic_vehicles",
    "build_geographic_vrp_problem",
]
