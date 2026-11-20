from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_super_admin
from app.core.database import get_db
from app.models import AdminUser
from app.schemas.dashboard import (
    DashboardOverview,
    LocationAnalytics,
    RecentActivityItem,
    ScanTrendItem,
)
from app.services.dashboard_service import (
    get_dashboard_overview,
    get_location_analytics,
    get_recent_activity,
    get_scan_trends,
)


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return get_dashboard_overview(db)


@router.get("/scan-trends", response_model=list[ScanTrendItem])
def dashboard_scan_trends(
    days: int = Query(default=30, ge=1, le=365),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return get_scan_trends(db, days=days)


@router.get("/location-analytics", response_model=LocationAnalytics)
def dashboard_location_analytics(
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return get_location_analytics(db)


@router.get("/recent-activity", response_model=list[RecentActivityItem])
def dashboard_recent_activity(
    limit: int = Query(default=10, ge=1, le=100),
    admin: AdminUser = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return get_recent_activity(db, limit=limit)
