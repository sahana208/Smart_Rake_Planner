from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Tuple
from ortools.linear_solver import pywraplp

# Data interfaces expected from DB
class Order:
    def __init__(self, order_id: str, product: str, quantity: float, due_date: datetime, priority: int, destination: str):
        self.order_id = order_id
        self.product = product
        self.quantity = quantity
        self.due_date = due_date
        self.priority = priority
        self.destination = destination

class Stockyard:
    def __init__(self, yard_id: str, material: str, available_quantity: float):
        self.yard_id = yard_id
        self.material = material
        self.available_quantity = available_quantity

class Vehicle:
    def __init__(self, id: str, type: str, capacity: float, available: int):
        self.id = id
        self.type = type
        self.capacity = capacity
        self.available = available

class Route:
    def __init__(self, id: str, origin: str, destination: str, mode: str, cost_per_ton_km: float, distance_km: float, transit_time: float):
        self.id = id
        self.origin = origin
        self.destination = destination
        self.mode = mode
        self.cost_per_ton_km = cost_per_ton_km
        self.distance_km = distance_km
        self.transit_time = transit_time  # in days

class OptimizationOutput:
    def __init__(self, total_cost: float, shipments: List[dict], mode_split: Dict[str, float], utilization: Dict[str, float]):
        self.total_cost = total_cost
        self.shipments = shipments
        self.mode_split = mode_split
        self.utilization = utilization


def run_optimization(
    orders: List[Order],
    stockyards: List[Stockyard],
    vehicles: List[Vehicle],
    routes: List[Route],
    late_penalty_per_ton_day: float = 50.0,
    alpha_transit: float = 0.5,
    beta_slack: float = 1.0,
) -> OptimizationOutput:
    # Build indices
    order_idx = {o.order_id: j for j, o in enumerate(orders)}
    yard_idx = {s.yard_id: i for i, s in enumerate(stockyards)}

    # Feasible arcs: stockyard -> order if route exists origin=yard destination=order.dest
    arcs: List[Tuple[int, int, Route]] = []
    routes_by_key: Dict[Tuple[str, str], List[Route]] = {}
    for r in routes:
        routes_by_key.setdefault((r.origin, r.destination), []).append(r)

    for s in stockyards:
        for o in orders:
            if (s.yard_id, o.destination) in routes_by_key:
                for r in routes_by_key[(s.yard_id, o.destination)]:
                    arcs.append((yard_idx[s.yard_id], order_idx[o.order_id], r))

    solver = pywraplp.Solver.CreateSolver("GLOP")  # Linear solver
    if solver is None:
        raise RuntimeError("Failed to create OR-Tools linear solver")

    # Decision variables x[i,j,mode] = tons shipped along a specific route (mode captured by route)
    x = {}
    for i, j, r in arcs:
        key = (i, j, r.id)
        x[key] = solver.NumVar(0.0, solver.infinity(), f"x_{i}_{j}_{r.id}")

    # Slack variables for lateness per order (in days-equivalent weighted by tons)
    delay = {}
    for o in orders:
        delay[o.order_id] = solver.NumVar(0.0, solver.infinity(), f"delay_{o.order_id}")

    # Objective: transport cost + penalty cost
    transport_terms = []
    for i, j, r in arcs:
        o = orders[j]
        cost_per_ton = r.cost_per_ton_km * r.distance_km
        transport_terms.append(x[(i, j, r.id)] * cost_per_ton)

    # Build dynamic penalty multipliers per order based on location (fastest transit) and slack to due date
    penalty_terms = []
    # Precompute fastest transit to each order destination among feasible arcs
    fastest_transit_by_order: Dict[str, float] = {}
    for o in orders:
        j = order_idx[o.order_id]
        fastest = None
        for (i, jj, r) in arcs:
            if jj == j:
                fastest = r.transit_time if fastest is None else min(fastest, r.transit_time)
        fastest_transit_by_order[o.order_id] = fastest if fastest is not None else 0.0

    now_days = 0.0  # reference; we use absolute day deltas below
    for o in orders:
        days_until_due = max((o.due_date - datetime.utcnow()).total_seconds() / 86400.0, 0.0)
        fastest_transit = fastest_transit_by_order.get(o.order_id, 0.0)
        # Location/urgency weighting:
        # - If fastest_transit > days_until_due, we scale up penalty linearly by the overage times alpha_transit
        # - If very little slack (days_until_due small), increase penalty using beta_slack / (days_until_due + 1)
        transit_overage = max(fastest_transit - days_until_due, 0.0)
        slack_component = beta_slack * (1.0 / (days_until_due + 1.0))
        multiplier = 1.0 + alpha_transit * transit_overage + slack_component
        penalty_terms.append(delay[o.order_id] * late_penalty_per_ton_day * multiplier)

    solver.Minimize(solver.Sum(transport_terms) + solver.Sum(penalty_terms))

    # Constraints
    # 1) Stockyard availability: sum_j,sum_routes x[i,j,route] <= available_stock[i]
    for s in stockyards:
        i = yard_idx[s.yard_id]
        flow = []
        for (ii, j, r) in arcs:
            if ii == i:
                flow.append(x[(ii, j, r.id)])
        solver.Add(solver.Sum(flow) <= s.available_quantity)

    # 2) Order fulfillment: sum_i,sum_routes x[i,j,route] >= order quantity - unmet (unmet captured implicitly by delay but we also bind delay)
    # Introduce equality between delivered tons and order quantity minus lateness impact.
    # To linearize, we link delay to shipments and due date via transit times.
    for o in orders:
        j = order_idx[o.order_id]
        incoming = []
        weighted_delay = []
        for (i, jj, r) in arcs:
            if jj == j:
                incoming.append(x[(i, jj, r.id)])
                # If ETA exceeds due date, define overage days factor; approximate with max(0, transit_time - time_left)
                days_until_due = max((o.due_date - datetime.utcnow()).total_seconds() / 86400.0, 0.0)
                lateness_factor = max(r.transit_time - days_until_due, 0.0)
                if lateness_factor > 0:
                    weighted_delay.append(x[(i, jj, r.id)] * lateness_factor)
        # Must deliver full quantity (we allow shortage only via delay variable representing late delivery measured in ton-days)
        solver.Add(solver.Sum(incoming) >= o.quantity)
        if weighted_delay:
            solver.Add(delay[o.order_id] >= solver.Sum(weighted_delay))
        else:
            solver.Add(delay[o.order_id] >= 0)

    # 3) Vehicle capacities by mode: sum shipments via mode per departure batch <= fleet capacity * capacity
    # We approximate daily capacity as available vehicles * capacity.
    mode_caps: Dict[str, Tuple[int, float]] = {}
    for v in vehicles:
        agg = mode_caps.get(v.type, (0, 0.0))
        mode_caps[v.type] = (agg[0] + v.available, v.capacity)

    for mode, (count, cap) in mode_caps.items():
        mode_flow = []
        for (i, j, r) in arcs:
            if ((mode == "rake" and r.mode == "rail") or
                (mode == "truck" and r.mode == "road") or
                (mode == "barge" and r.mode == "water")):
                mode_flow.append(x[(i, j, r.id)])
        solver.Add(solver.Sum(mode_flow) <= count * cap)

    # Solve
    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL and status != pywraplp.Solver.FEASIBLE:
        raise RuntimeError("No feasible solution found by the solver")

    # Build result
    shipments: List[dict] = []
    mode_split: Dict[str, float] = {"rail": 0.0, "road": 0.0, "water": 0.0}

    for (i, j, r) in arcs:
        qty = x[(i, j, r.id)].solution_value()
        if qty <= 1e-6:
            continue
        o = orders[j]
        s = stockyards[i]
        cost = r.cost_per_ton_km * r.distance_km * qty
        days_until_due = max((o.due_date - datetime.utcnow()).total_seconds() / 86400.0, 0.0)
        on_time = r.transit_time <= days_until_due + 1e-6
        shipments.append({
            "order_id": o.order_id,
            "stockyard_id": s.yard_id,
            "mode": r.mode,
            "quantity": qty,
            "cost": cost,
            "eta_days": r.transit_time,
            "on_time": on_time,
        })
        mode_split[r.mode] += qty

    total_cost = solver.Objective().Value()

    # Utilization by mode (% of capacity used)
    utilization = {}
    for mode, (count, cap) in mode_caps.items():
        denom = max(count * cap, 1e-6)
        shipped = 0.0
        for sh in shipments:
            if ((mode == "rake" and sh["mode"] == "rail") or
                (mode == "truck" and sh["mode"] == "road") or
                (mode == "barge" and sh["mode"] == "water")):
                shipped += sh["quantity"]
        utilization[mode] = shipped / denom

    return OptimizationOutput(total_cost=total_cost, shipments=shipments, mode_split=mode_split, utilization=utilization)
