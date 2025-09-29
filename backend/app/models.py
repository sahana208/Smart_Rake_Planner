from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal

# Pydantic schemas for API layer

class OrderIn(BaseModel):
    order_id: str
    product: str
    quantity: float = Field(ge=0)
    due_date: datetime
    priority: int = Field(ge=1, le=5)
    destination: str

class Order(OrderIn):
    id: Optional[str] = None

class StockyardIn(BaseModel):
    yard_id: str
    material: str
    available_quantity: float = Field(ge=0)

class Stockyard(StockyardIn):
    id: Optional[str] = None

class VehicleIn(BaseModel):
    id: str
    type: Literal["rake", "truck", "barge"]
    capacity: float = Field(ge=0)
    available: int = Field(ge=0)

class Vehicle(VehicleIn):
    _id: Optional[str] = None

class RouteIn(BaseModel):
    id: str
    origin: str
    destination: str
    mode: Literal["rail", "road", "water"]
    cost_per_ton_km: float = Field(ge=0)
    distance_km: float = Field(ge=0)
    transit_time: float = Field(ge=0, description="Transit time in days")

class Route(RouteIn):
    _id: Optional[str] = None

# Response models for optimization
class OptimizationRequest(BaseModel):
    # optional tuning parameters
    late_penalty_per_ton_day: float = 50.0
    # Dynamic weighting of lateness penalty per order (priority derived from location/urgency)
    # alpha_transit penalizes orders whose fastest available route has long transit time relative to due date
    alpha_transit: float = 0.5
    # beta_slack penalizes low slack (days_until_due). Higher when due soon.
    beta_slack: float = 1.0

class ShipmentPlanItem(BaseModel):
    order_id: str
    stockyard_id: str
    mode: Literal["rail", "road", "water"]
    quantity: float
    cost: float
    on_time: bool
    eta_days: float

class OptimizationResult(BaseModel):
    total_cost: float
    mode_split: dict
    utilization: dict
    shipments: list[ShipmentPlanItem]

# Simplified plan API
class PlanRequest(BaseModel):
    quantity: float = Field(ge=0)
    delivery_date: datetime
    penalty_cost: float = Field(ge=0, description="₹ per ton-day")
    destination: str

class PlanResult(BaseModel):
    chosen_stockyard: str
    mode: Literal["rail", "road", "water", "air"]
    route_id: str
    estimated_cost: float
    estimated_arrival: datetime
    penalty_avoided: bool
    total_cost_with_penalty: float
    alternatives: list[dict] = []
