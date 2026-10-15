from fastapi import APIRouter
from api.v1.subscribers import router as subscribers_router
from api.v1.payments import router as payments_router
from api.v1.capital import router as capital_router
from api.v1.draw import router as draw_router
from api.v1.stats import router as stats_router

api_v1_router = APIRouter()

api_v1_router.include_router(subscribers_router)
api_v1_router.include_router(payments_router)
api_v1_router.include_router(capital_router)
api_v1_router.include_router(draw_router)
api_v1_router.include_router(stats_router)
