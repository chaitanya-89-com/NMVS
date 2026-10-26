from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from . import service
from .schema import DashboardOverviewResponse, DashboardStats

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=DashboardOverviewResponse,
    summary="Get complete dashboard overview"
)
@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    summary="Get complete dashboard overview (alias)"
)
def get_dashboard_overview():
    """
    Retrieve aggregated dashboard payload including KPI cards,
    device distribution by type, recent monitoring events, and bandwidth speeds.
    """
    try:
        return service.get_dashboard_overview()
    except Exception as e:
        print(f"DASHBOARD OVERVIEW ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard overview: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=DashboardStats,
    summary="Get quick KPI dashboard statistics"
)
def get_dashboard_stats():
    """
    Retrieve key performance indicator stats (total, online, offline devices, health score, subnets).
    """
    try:
        return service.get_dashboard_stats()
    except Exception as e:
        print(f"DASHBOARD STATS ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard stats: {str(e)}"
        )
