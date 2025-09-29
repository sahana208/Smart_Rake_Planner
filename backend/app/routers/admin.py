from fastapi import APIRouter, Depends
from ..db import get_db
from ..init_db import ensure_indexes

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/ping")
async def ping(db = Depends(get_db)):
    # simple roundtrip
    await db.command("ping")
    return {"status": "ok"}

@router.post("/init")
async def init(db = Depends(get_db)):
    diag = await ensure_indexes(db)
    return {"status": "initialized", **diag}

@router.post("/seed")
async def seed(db = Depends(get_db)):
    # Minimal demo data
    await ensure_indexes(db)

    orders = [
        {"order_id": "O1", "product": "coil", "quantity": 1000, "due_date": "2030-01-05T00:00:00Z", "priority": 3, "destination": "CMO1"},
        {"order_id": "O2", "product": "plate", "quantity": 600, "due_date": "2030-01-03T00:00:00Z", "priority": 4, "destination": "CMO2"},
    ]
    yards = [
        {"yard_id": "BOKARO", "material": "coil", "available_quantity": 2000},
        {"yard_id": "BOKARO2", "material": "plate", "available_quantity": 1200},
    ]
    vehicles = [
        {"id": "T1", "type": "truck", "capacity": 20, "available": 50},
        {"id": "R1", "type": "rake", "capacity": 3500, "available": 1},
        {"id": "B1", "type": "barge", "capacity": 1000, "available": 2},
    ]
    routes = [
        {"id": "R_BOK_CMO1", "origin": "BOKARO", "destination": "CMO1", "mode": "rail", "cost_per_ton_km": 0.9, "distance_km": 400, "transit_time": 1.5},
        {"id": "RD_BOK_CMO1", "origin": "BOKARO", "destination": "CMO1", "mode": "road", "cost_per_ton_km": 1.2, "distance_km": 400, "transit_time": 2.5},
        {"id": "W_BOK_CMO1", "origin": "BOKARO", "destination": "CMO1", "mode": "water", "cost_per_ton_km": 0.7, "distance_km": 600, "transit_time": 4.5},
        {"id": "R_BOK2_CMO2", "origin": "BOKARO2", "destination": "CMO2", "mode": "rail", "cost_per_ton_km": 0.85, "distance_km": 500, "transit_time": 2.0},
        {"id": "RD_BOK2_CMO2", "origin": "BOKARO2", "destination": "CMO2", "mode": "road", "cost_per_ton_km": 1.1, "distance_km": 500, "transit_time": 3.0},
    ]

    for o in orders:
        await db.orders.update_one({"order_id": o["order_id"]}, {"$set": o}, upsert=True)
    for y in yards:
        await db.stockyards.update_one({"yard_id": y["yard_id"]}, {"$set": y}, upsert=True)
    for v in vehicles:
        await db.vehicles.update_one({"id": v["id"]}, {"$set": v}, upsert=True)
    for r in routes:
        await db.routes.update_one({"id": r["id"]}, {"$set": r}, upsert=True)

    return {"status": "seeded"}

@router.get("/history")
async def history(db = Depends(get_db)):
    plans = await db.plans.find().sort("created_at", -1).limit(50).to_list(50)
    orders = await db.orders.find().sort("_id", -1).limit(50).to_list(50)
    # Convert ObjectId to string for orders
    for o in orders:
        if o.get("_id"):
            o["_id"] = str(o["_id"])
    return {"plans": plans, "orders": orders}
