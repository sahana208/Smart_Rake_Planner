from fastapi import APIRouter, Depends
from typing import List
from ..db import get_db
from ..models import Stockyard, StockyardIn

router = APIRouter(prefix="/stockyards", tags=["stockyards"])

@router.get("/", response_model=List[Stockyard])
async def list_stockyards(db = Depends(get_db)):
    docs = await db.stockyards.find().to_list(1000)
    return [Stockyard(**{**d, "id": str(d.get("_id"))}) for d in docs]

@router.post("/", response_model=Stockyard)
async def create_stockyard(payload: StockyardIn, db = Depends(get_db)):
    data = payload.model_dump()
    await db.stockyards.update_one({"yard_id": data["yard_id"]}, {"$set": data}, upsert=True)
    doc = await db.stockyards.find_one({"yard_id": data["yard_id"]})
    return Stockyard(**{**doc, "id": str(doc.get("_id"))})

@router.delete("/{yard_id}")
async def delete_stockyard(yard_id: str, db = Depends(get_db)):
    await db.stockyards.delete_one({"yard_id": yard_id})
    return {"status": "ok"}
