from fastapi import APIRouter
from app.api.v1.endpoints import auth, reports, cases

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports & Duplicates"])
api_router.include_router(cases.router, prefix="/cases", tags=["Cases & Accountability"])
