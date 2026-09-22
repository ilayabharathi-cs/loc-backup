from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.dashboard import DashboardSummaryResponse
from app.schemas.common import ApiResponse
from app.services.dashboard_service import get_dashboard_summary
from app.security.dependencies import get_optional_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=ApiResponse[DashboardSummaryResponse])
def get_summary(db: Session = Depends(get_db), current_user=Depends(get_optional_current_user)):
    summary = get_dashboard_summary(db)
    return ApiResponse(
        success=True,
        data=summary,
        message="Dashboard summary metrics aggregated successfully"
    )
