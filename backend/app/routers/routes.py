from fastapi import APIRouter, Depends
from typing import List
from ..db import get_db
from ..models import Route, RouteIn

router = APIRouter(prefix="/routes", tags=["routes"])

@router.get("/", response_model=List[Route])
async def list_routes(db = Depends(get_db)):
    docs = await db.routes.find().to_list(1000)
    return [Route(**{**d, "_id": str(d.get("_id"))}) for d in docs]

@router.post("/", response_model=Route)
async def create_route(payload: RouteIn, db = Depends(get_db)):
    data = payload.model_dump()
    await db.routes.update_one({"id": data["id"]}, {"$set": data}, upsert=True)
    doc = await db.routes.find_one({"id": data["id"]})
    return Route(**{**doc, "_id": str(doc.get("_id"))})

@router.delete("/{route_id}")
async def delete_route(route_id: str, db = Depends(get_db)):
    await db.routes.delete_one({"id": route_id})
    return {"status": "ok"}
