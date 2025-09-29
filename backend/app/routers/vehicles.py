from fastapi import APIRouter, Depends
from typing import List
from ..db import get_db
from ..models import Vehicle, VehicleIn

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

@router.get("/", response_model=List[Vehicle])
async def list_vehicles(db = Depends(get_db)):
    docs = await db.vehicles.find().to_list(1000)
    return [Vehicle(**{**d, "_id": str(d.get("_id"))}) for d in docs]

@router.post("/", response_model=Vehicle)
async def create_vehicle(payload: VehicleIn, db = Depends(get_db)):
    data = payload.model_dump()
    await db.vehicles.update_one({"id": data["id"]}, {"$set": data}, upsert=True)
    doc = await db.vehicles.find_one({"id": data["id"]})
    return Vehicle(**{**doc, "_id": str(doc.get("_id"))})

@router.delete("/{vehicle_id}")
async def delete_vehicle(vehicle_id: str, db = Depends(get_db)):
    await db.vehicles.delete_one({"id": vehicle_id})
    return {"status": "ok"}
