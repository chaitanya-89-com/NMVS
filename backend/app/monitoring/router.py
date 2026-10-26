from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import IPvAnyAddress

from app.dependencies import get_current_user
from . import service
from .schema import DeviceAvailability, MonitoringResponse


router = APIRouter(
    prefix="/monitoring",
    tags=["Monitoring"],
    dependencies=[Depends(get_current_user)],
)


# =========================================================
# CHECK DEVICE NOW
# =========================================================

@router.get(
    "/check/{ip}",
    response_model=MonitoringResponse
)
def check_device(ip: IPvAnyAddress):

    result = service.check_and_save_device(str(ip))

    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to monitor device"
        )

    return result


# =========================================================
# GET MONITORING HISTORY
# =========================================================

@router.get(
    "/history/{ip}",
    response_model=list[MonitoringResponse]
)
def get_monitoring_history(
    ip: IPvAnyAddress,
    limit: int = Query(default=100, ge=1, le=5000),
    days: int | None = Query(default=None, ge=1, le=30),
):

    history = service.get_monitoring_history(
        str(ip),
        limit,
        days,
    )

    return history


# =========================================================
# GET ALL MONITORING HISTORY
# =========================================================

@router.get(
    "/history",
    response_model=list[MonitoringResponse]
)
def get_all_monitoring_history(
    limit: int = Query(default=100, ge=1, le=5000),
    days: int | None = Query(default=None, ge=1, le=30),
):

    return service.get_all_monitoring_history(
        limit,
        days,
    )


@router.delete("/history")
def clear_monitoring_history():
    """Delete monitoring records while preserving registered devices and alerts."""
    deleted_count = service.clear_monitoring_history()
    return {"deleted_count": deleted_count}


@router.get(
    "/availability",
    response_model=list[DeviceAvailability],
)
def get_device_availability(days: int = Query(default=7, ge=1, le=30)):
    """Return check-based uptime and latency summaries for registered devices."""
    if days not in {1, 7, 30}:
        raise HTTPException(
            status_code=422,
            detail="days must be one of 1, 7, or 30",
        )
    return service.get_availability(days)