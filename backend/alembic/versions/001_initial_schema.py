"""Initial schema migration: networks, nodes, edges, fleet_vehicles, customers, optimization_runs, routes, incidents.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-29 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Helper for JSON / JSONB
    json_col = sa.JSON().with_variant(JSONB, 'postgresql')

    # 1. networks table
    op.create_table(
        'networks',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, server_default='Synthetic Network'),
        sa.Column('n_nodes', sa.Integer(), nullable=False),
        sa.Column('n_edges', sa.Integer(), nullable=False),
        sa.Column('n_depots', sa.Integer(), nullable=False),
        sa.Column('n_customers', sa.Integer(), nullable=False),
        sa.Column('n_intersections', sa.Integer(), nullable=False),
        sa.Column('seed', sa.Integer(), nullable=False),
        sa.Column('connect_radius_km', sa.Float(), nullable=False),
        sa.Column('grid_size_km', sa.Float(), nullable=False),
        sa.Column('closed_fraction', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_networks_is_active', 'networks', ['is_active'])

    # 2. nodes table
    op.create_table(
        'nodes',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('network_id', sa.String(length=36), sa.ForeignKey('networks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_id', sa.String(length=64), nullable=False),
        sa.Column('node_type', sa.String(length=32), nullable=False),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
    )
    op.create_index('ix_nodes_network_id', 'nodes', ['network_id'])
    op.create_index('ix_nodes_network_node_id', 'nodes', ['network_id', 'node_id'])

    # 3. edges table
    op.create_table(
        'edges',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('network_id', sa.String(length=36), sa.ForeignKey('networks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('u', sa.String(length=64), nullable=False),
        sa.Column('v', sa.String(length=64), nullable=False),
        sa.Column('distance', sa.Float(), nullable=False),
        sa.Column('base_travel_time', sa.Float(), nullable=False),
        sa.Column('congestion_factor', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('road_status', sa.String(length=32), nullable=False, server_default='open'),
    )
    op.create_index('ix_edges_network_id', 'edges', ['network_id'])
    op.create_index('ix_edges_network_u_v', 'edges', ['network_id', 'u', 'v'])

    # 4. fleet_vehicles table
    op.create_table(
        'fleet_vehicles',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('network_id', sa.String(length=36), sa.ForeignKey('networks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vehicle_id', sa.String(length=64), nullable=False),
        sa.Column('capacity', sa.Float(), nullable=False),
        sa.Column('depot_node', sa.String(length=64), nullable=False),
    )
    op.create_index('ix_fleet_vehicles_network_id', 'fleet_vehicles', ['network_id'])

    # 5. customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('network_id', sa.String(length=36), sa.ForeignKey('networks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('customer_id', sa.String(length=64), nullable=False),
        sa.Column('location_node', sa.String(length=64), nullable=False),
        sa.Column('demand', sa.Float(), nullable=False),
    )
    op.create_index('ix_customers_network_id', 'customers', ['network_id'])

    # 6. optimization_runs table
    op.create_table(
        'optimization_runs',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('network_id', sa.String(length=36), sa.ForeignKey('networks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('seed', sa.Integer(), nullable=False),
        sa.Column('n_particles', sa.Integer(), nullable=False),
        sa.Column('max_iterations', sa.Integer(), nullable=False),
        sa.Column('w_time', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('w_distance', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('w_congestion', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('best_fitness', sa.Float(), nullable=False),
        sa.Column('is_feasible', sa.Boolean(), nullable=False),
        sa.Column('n_iterations_run', sa.Integer(), nullable=False),
        sa.Column('stopped_early', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('pre_repair_fitness', sa.Float(), nullable=True),
        sa.Column('post_repair_fitness', sa.Float(), nullable=True),
        sa.Column('convergence_history', json_col, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_optimization_runs_network_id', 'optimization_runs', ['network_id'])
    op.create_index('ix_optimization_runs_created_at', 'optimization_runs', ['created_at'])

    # 7. routes table
    op.create_table(
        'routes',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('optimization_run_id', sa.String(length=36), sa.ForeignKey('optimization_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('route_id', sa.String(length=64), nullable=False),
        sa.Column('vehicle_id', sa.String(length=64), nullable=False),
        sa.Column('depot_node', sa.String(length=64), nullable=False),
        sa.Column('visit_order', json_col, nullable=False),
        sa.Column('node_sequence', json_col, nullable=False),
        sa.Column('total_distance', sa.Float(), nullable=False),
        sa.Column('total_travel_time', sa.Float(), nullable=False),
        sa.Column('estimated_arrival', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_routes_optimization_run_id', 'routes', ['optimization_run_id'])
    op.create_index('ix_routes_status', 'routes', ['status'])

    # 8. incidents table
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('network_id', sa.String(length=36), sa.ForeignKey('networks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('optimization_run_id', sa.String(length=36), sa.ForeignKey('optimization_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('edge_u', sa.String(length=64), nullable=False),
        sa.Column('edge_v', sa.String(length=64), nullable=False),
        sa.Column('incident_type', sa.String(length=32), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_closure', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_incidents_network_id', 'incidents', ['network_id'])
    op.create_index('ix_incidents_is_active', 'incidents', ['is_active'])


def downgrade() -> None:
    op.drop_table('incidents')
    op.drop_table('routes')
    op.drop_table('optimization_runs')
    op.drop_table('customers')
    op.drop_table('fleet_vehicles')
    op.drop_table('edges')
    op.drop_table('nodes')
    op.drop_table('networks')
