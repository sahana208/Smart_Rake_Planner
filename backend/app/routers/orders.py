from fastapi import APIRouter, Depends
from typing import List
from ..db import get_db
from ..models import Order, OrderIn

router = APIRouter(prefix="/orders", tags=["orders"])

@router.get("/", response_model=List[Order])
async def list_orders(db = Depends(get_db)):
    docs = await db.orders.find().to_list(1000)
    return [Order(**{**d, "id": str(d.get("_id"))}) for d in docs]

@router.post("/", response_model=Order)
async def create_order(payload: OrderIn, db = Depends(get_db)):
    data = payload.model_dump()
    await db.orders.update_one({"order_id": data["order_id"]}, {"$set": data}, upsert=True)
    doc = await db.orders.find_one({"order_id": data["order_id"]})
    return Order(**{**doc, "id": str(doc.get("_id"))})

@router.delete("/{order_id}")
async def delete_order(order_id: str, db = Depends(get_db)):
    await db.orders.delete_one({"order_id": order_id})
    return {"status": "ok"}
