from motor.motor_asyncio import AsyncIOMotorDatabase

async def ensure_indexes(db: AsyncIOMotorDatabase):
    # Ensure collections exist explicitly, then create indexes
    wanted = ["orders", "stockyards", "vehicles", "routes", "plans"]
    existing = set(await db.list_collection_names())
    created = []
    for name in wanted:
        if name not in existing:
            await db.create_collection(name)
            created.append(name)

    # Unique identifiers
    await db.orders.create_index("order_id", unique=True)
    await db.stockyards.create_index("yard_id", unique=True)
    await db.vehicles.create_index("id", unique=True)
    await db.routes.create_index("id", unique=True)

    # Helpful additional indexes
    await db.orders.create_index([("destination", 1)])
    await db.routes.create_index([("origin", 1), ("destination", 1), ("mode", 1)])

    # Plans auditing indexes
    await db.plans.create_index([("created_at", 1)])

    return {"created_collections": created, "all_collections": await db.list_collection_names()}
