"""FastAPI microservice for checkout recommendations.   uvicorn retail_basket.api:app --port 8001   (or: make retail-api)

POST /recommend  {"cart": ["D7050", "Bosch DS160 Detector"], "k": 5}   -> ranked items with confidence, lift, support and a reason;
                 status "no_pattern" with an empty list when the cart combination has no reliable history (nothing irrelevant is shown)
GET  /items      product catalog          GET /health  liveness + model version
GET  /metrics    request count, no-pattern rate, latency (monitoring)
POST /orders     record a completed order (learned at the next retrain)
POST /retrain    reload the orders CSV plus logged orders and refit (periodic retraining)
"""
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from retail_basket.service import RecommenderService

app = FastAPI(title="Suggest IQ Retail: market-basket recommendations", version="1.0")
_service: Optional[RecommenderService] = None


def service() -> RecommenderService:
    global _service
    if _service is None:
        _service = RecommenderService()
    return _service


class RecommendRequest(BaseModel):
    cart: List[str] = Field(default_factory=list, description="SKUs or product names already in the cart")
    k: int = Field(5, ge=1, le=20)


class RecommendationOut(BaseModel):
    sku: str
    name: str
    confidence: float
    lift: float
    orders_with_both: int
    orders_with_cart: int
    reason: str


class RecommendResponse(BaseModel):
    status: str
    message: str
    cart: List[str]
    recommendations: List[RecommendationOut]


@app.get("/health")
def health():
    return {"status": "ok", **service().info()}


@app.get("/items")
def items():
    return [{"sku": i.sku, "name": i.name, "brand": i.brand} for i in service().catalog.values()]


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    svc = service()
    try:
        result = svc.recommend(req.cart, req.k)
        skus = [svc.resolve(c) for c in req.cart]
    except KeyError as err:
        raise HTTPException(status_code=422, detail=f"Unknown item: {err.args[0]}")
    return RecommendResponse(
        status=result.status, message=result.message, cart=skus,
        recommendations=[RecommendationOut(sku=r.sku, name=svc.catalog[r.sku].name, confidence=round(r.confidence, 4), lift=round(r.lift, 3),
                                           orders_with_both=r.count, orders_with_cart=r.cart_support, reason=r.reason()) for r in result.recs])


class OrderRequest(BaseModel):
    cart: List[str] = Field(..., min_length=2, description="SKUs or names of the items in the completed order")


@app.post("/orders")
def place_order(req: OrderRequest):
    """Record a completed order; it is learned from at the next POST /retrain."""
    try:
        skus = service().log_order(req.cart)
    except KeyError as err:
        raise HTTPException(status_code=422, detail=f"Unknown item: {err.args[0]}")
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    return {"logged": skus, **service().info()}


@app.get("/metrics")
def metrics():
    return service().metrics()


@app.post("/retrain")
def retrain():
    return service().retrain()
