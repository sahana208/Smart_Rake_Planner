from datetime import datetime
from fastapi import APIRouter, Depends
from ..db import get_db
from ..models import OptimizationRequest, OptimizationResult
from ..optimization import run_optimization, Order, Stockyard, Vehicle, Route

router = APIRouter(prefix="/optimize", tags=["optimize"])

@router.post("/", response_model=OptimizationResult)
async def optimize(req: OptimizationRequest, db = Depends(get_db)):
    # Fetch data from MongoDB
    orders_docs = await db.orders.find().to_list(10000)
    yards_docs = await db.stockyards.find().to_list(10000)
    vehicles_docs = await db.vehicles.find().to_list(10000)
    routes_docs = await db.routes.find().to_list(10000)

    # Map to optimization DTOs
    orders = [Order(
        order_id=d["order_id"],
        product=d["product"],
        quantity=float(d["quantity"]),
        due_date=datetime.fromisoformat(d["due_date"]) if isinstance(d["due_date"], str) else d["due_date"],
        priority=int(d["priority"]),
        destination=d["destination"],
    ) for d in orders_docs]

    stockyards = [Stockyard(
        yard_id=d["yard_id"],
        material=d["material"],
        available_quantity=float(d["available_quantity"]),
    ) for d in yards_docs]

    vehicles = [Vehicle(
        id=d["id"],
        type=d["type"],
        capacity=float(d["capacity"]),
        available=int(d["available"]),
    ) for d in vehicles_docs]

    routes = [Route(
        id=d["id"],
        origin=d["origin"],
        destination=d["destination"],
        mode=d["mode"],
        cost_per_ton_km=float(d["cost_per_ton_km"]),
        distance_km=float(d["distance_km"]),
        transit_time=float(d["transit_time"]),
    ) for d in routes_docs]

    out = run_optimization(
        orders=orders,
        stockyards=stockyards,
        vehicles=vehicles,
        routes=routes,
        late_penalty_per_ton_day=req.late_penalty_per_ton_day,
        alpha_transit=req.alpha_transit,
        beta_slack=req.beta_slack,
    )

    # Build response
    return OptimizationResult(
        total_cost=out.total_cost,
        shipments=[
            {
                "order_id": s["order_id"],
                "stockyard_id": s["stockyard_id"],
                "mode": s["mode"],
                "quantity": s["quantity"],
                "cost": s["cost"],
                "on_time": s["on_time"],
                "eta_days": s["eta_days"],
            }
            for s in out.shipments
        ],
        mode_split=out.mode_split,
        utilization=out.utilization,
    )
