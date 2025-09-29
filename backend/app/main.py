from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import close_db, get_db
from .routers import orders, stockyards, vehicles, routes, optimize
from .routers import admin
from .routers import plan
from .init_db import ensure_indexes

app = FastAPI(title="Logistics Optimization API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router)
app.include_router(stockyards.router)
app.include_router(vehicles.router)
app.include_router(routes.router)
app.include_router(optimize.router)
app.include_router(admin.router)
app.include_router(plan.router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "Logistics Optimization API"}

@app.on_event("startup")
async def startup_event():
    db = await get_db()
    await ensure_indexes(db)

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()
