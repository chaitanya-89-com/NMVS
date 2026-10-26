import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user
from . import service
from .schema import (
    DeviceSpeedTestJobResponse,
    DeviceSpeedTestRequest,
    SpeedTestHistoryItem,
    SpeedTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/speed-monitoring",
    tags=["Speed Monitoring"],
    dependencies=[Depends(get_current_user)],
)


# ==================================================
# 1. RUN SPEED TEST & SAVE TO HISTORY
# ==================================================

@router.post(
    "/run",
    response_model=DeviceSpeedTestJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_and_save_speed_test(request: DeviceSpeedTestRequest):
    """
    Queue a device-local speed test for a recently Online agent-owned device.
    """
    try:
        return service.request_device_test(str(request.ip))
    except service.InvalidDeviceIPv4 as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except service.DeviceOutsideConfiguredNetwork as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error while queuing a device speed test")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to start the device speed test.",
        ) from e


@router.get("/jobs/{job_id}", response_model=DeviceSpeedTestJobResponse)
def get_device_speed_test_job(job_id: int):
    job = service.get_device_test_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Speed test job not found.")
    return job


# ==================================================
# 2. RUN LIVE SPEED TEST (NO SAVING)
# ==================================================

@router.get(
    "/live",
    response_model=SpeedTestResponse
)
def run_live_speed_test():
    """
    Run a live speed test (download, upload, ping) without saving to database.
    """
    try:
        return service.run_live_test()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speed test failed: {str(e)}"
        )


# ==================================================
# 3. SPEED TEST HISTORY
# ==================================================

@router.get(
    "/history",
    response_model=list[SpeedTestHistoryItem]
)
def get_speed_test_history(
    limit: int = Query(default=20, ge=1, le=100),
    ip: str = Query(default=None, description="Filter by stored source label; not a device measurement")
):
    """
    Retrieve past speed test history records.
    """
    try:
        return service.get_history(limit=limit, ip=ip)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )


@router.get(
    "/history/{history_id}",
    response_model=SpeedTestHistoryItem
)
def get_speed_test_record(history_id: int):
    """
    Retrieve a specific speed test record by ID.
    """
    record = service.get_history_by_id(history_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History record not found"
        )
    return record


@router.delete(
    "/history/{history_id}"
)
def delete_speed_test_history(history_id: int):
    """
    Delete a specific speed test history record.
    """
    deleted = service.delete_history(history_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History record not found"
        )
    return {"message": "Speed test history record deleted successfully"}