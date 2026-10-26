from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user
from . import service
from .schema import DeviceUptimeMetric, NetworkMetricsSummary

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/summary",
    response_model=NetworkMetricsSummary,
    summary="Get overall network metrics summary"
)
def get_metrics_summary():
    """
    Retrieve overall network performance metrics:
    Uptime percentage, average latency, bandwidth averages,
    and healthy vs degraded device breakdown.
    """
    try:
        return service.get_metrics_summary()
    except Exception as e:
        print(f"METRICS SUMMARY ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate metrics summary"
        )


@router.get(
    "/uptime",
    response_model=list[DeviceUptimeMetric],
    summary="Get device uptime and availability percentages"
)
def get_devices_uptime(
    hours: int = Query(default=24, ge=1, le=720, description="Rolling time window in hours (default 24h)")
):
    """
    Retrieve availability percentages, total checks, online/offline counts
    for every registered device over the specified time window.
    """
    try:
        return service.get_devices_uptime(hours=hours)
    except Exception as e:
        print(f"METRICS UPTIME ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate device uptime metrics"
        )
