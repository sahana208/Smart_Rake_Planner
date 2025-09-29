from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from ..db import get_db
from ..models import PlanRequest, PlanResult

router = APIRouter(prefix="/plan", tags=["plan"])


async def _load_or_defaults(db):
    stockyards = await db.stockyards.find().to_list(1000)
    routes = await db.routes.find().to_list(5000)
    vehicles = await db.vehicles.find().to_list(1000)

    # Provide sane defaults if empty
    if not stockyards:
        stockyards = [
            {"yard_id": "BOKARO", "material": "steel", "available_quantity": 5000},
        ]
    if not routes:
        routes = [
            {"id": "R_BOK_CMO1", "origin": "BOKARO", "destination": "CMO1", "mode": "rail", "cost_per_ton_km": 0.9, "distance_km": 400, "transit_time": 1.5},
            {"id": "RD_BOK_CMO1", "origin": "BOKARO", "destination": "CMO1", "mode": "road", "cost_per_ton_km": 1.2, "distance_km": 400, "transit_time": 2.5},
            {"id": "W_BOK_CMO1", "origin": "BOKARO", "destination": "CMO1", "mode": "water", "cost_per_ton_km": 0.7, "distance_km": 600, "transit_time": 4.5},
            {"id": "A_BOK_CMO1", "origin": "BOKARO", "destination": "CMO1", "mode": "air", "cost_per_ton_km": 2.8, "distance_km": 400, "transit_time": 0.5},
        ]
    if not vehicles:
        vehicles = [
            {"id": "T1", "type": "truck", "capacity": 20, "available": 50},
            {"id": "R1", "type": "rake", "capacity": 3500, "available": 1},
            {"id": "B1", "type": "barge", "capacity": 1000, "available": 2},
        ]
    return stockyards, routes, vehicles


@router.post("/", response_model=PlanResult)
async def create_plan(req: PlanRequest, db = Depends(get_db)):
    yards, routes, vehicles = await _load_or_defaults(db)

    # Map mode names
    mode_map = {"rake": "rail", "truck": "road", "barge": "water"}
    # Daily capacity by mode (available * capacity)
    mode_capacity = {"rail": 0.0, "road": 0.0, "water": 0.0}
    for v in vehicles:
        m = mode_map.get(v.get("type"), v.get("type"))
        if m in mode_capacity:
            mode_capacity[m] += float(v.get("available", 0)) * float(v.get("capacity", 0))

    # Feasible route candidates from any yard to destination
    candidates = []
    for y in yards:
        for r in routes:
            if r.get("origin") == y.get("yard_id") and r.get("destination") == req.destination:
                m = r.get("mode")
                if m not in mode_capacity:
                    continue
                if float(y.get("available_quantity", 0)) < req.quantity:
                    continue  # not enough stock
                if mode_capacity[m] < req.quantity:
                    continue  # not enough transport capacity
                cost = float(r["cost_per_ton_km"]) * float(r["distance_km"]) * float(req.quantity)
                eta = datetime.utcnow() + timedelta(days=float(r["transit_time"]))
                days_late = max((eta - req.delivery_date).total_seconds() / 86400.0, 0.0)
                penalty = days_late * float(req.penalty_cost) * float(req.quantity)
                total = cost + penalty
                candidates.append({
                    "yard_id": y["yard_id"],
                    "route_id": r["id"],
                    "mode": r["mode"],
                    "cost": cost,
                    "eta": eta,
                    "penalty": penalty,
                    "total": total,
                })

    if not candidates:
        raise HTTPException(status_code=400, detail="No feasible route/stockyard/vehicle capacity for the requested plan")

    # Dummy optimizer: pick min total cost (transport + penalty)
    candidates_sorted = sorted(candidates, key=lambda c: c["total"])[:3]
    best = candidates_sorted[0]
    alternatives = candidates_sorted[1:]

    # Persist order input + computed result
    order_doc = {
        "order_id": f"AUTO-{int(datetime.utcnow().timestamp())}",
        "product": "steel",
        "quantity": req.quantity,
        "due_date": req.delivery_date,
        "priority": 3,
        "destination": req.destination,
        "plan": {
            "stockyard": best["yard_id"],
            "route_id": best["route_id"],
            "mode": best["mode"],
            "estimated_cost": best["cost"],
            "estimated_arrival": best["eta"],
            "penalty": best["penalty"],
            "total": best["total"],
            "penalty_cost": req.penalty_cost,
        }
    }
    await db.orders.insert_one(order_doc)

    # Persist a detailed plan audit record
    plan_audit = {
        "created_at": datetime.utcnow(),
        "input": {
            "quantity": req.quantity,
            "delivery_date": req.delivery_date,
            "penalty_cost": req.penalty_cost,
            "destination": req.destination,
        },
        "computed": {
            "chosen_stockyard": best["yard_id"],
            "mode": best["mode"],
            "route_id": best["route_id"],
            "estimated_cost": best["cost"],
            "estimated_arrival": best["eta"],
            "penalty": best["penalty"],
            "total_cost_with_penalty": best["total"],
            "alternatives": [
                {
                    "stockyard": alt["yard_id"],
                    "mode": alt["mode"],
                    "route_id": alt["route_id"],
                    "estimated_cost": alt["cost"],
                    "estimated_arrival": alt["eta"],
                    "penalty": alt["penalty"],
                    "total": alt["total"],
                } for alt in alternatives
            ]
        }
    }
    await db.plans.insert_one(plan_audit)

    return PlanResult(
        chosen_stockyard=best["yard_id"],
        mode=best["mode"],
        route_id=best["route_id"],
        estimated_cost=best["cost"],
        estimated_arrival=best["eta"],
        penalty_avoided=best["penalty"] <= 1e-6,
        total_cost_with_penalty=best["total"],
        alternatives=[
            {
                "stockyard": alt["yard_id"],
                "mode": alt["mode"],
                "route_id": alt["route_id"],
                "estimated_cost": alt["cost"],
                "estimated_arrival": alt["eta"],
                "penalty": alt["penalty"],
                "total": alt["total"],
            } for alt in alternatives
        ]
    )
