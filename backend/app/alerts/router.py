from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user
from . import service
from .schema import AlertCreate, AlertResponse, AlertsSummary

router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[AlertResponse],
    summary="Get all alerts with optional status, severity, and alert_type filters"
)
def get_alerts(
    status: str | None = Query(
        default=None,
        description="Filter by status: active, acknowledged, resolved"
    ),
    severity: str | None = Query(
        default=None,
        description="Filter by severity: critical, warning, info"
    ),
    alert_type: str | None = Query(
        default=None,
        description="Filter by type: DISCONNECTED, CONNECTED, HIGH_LATENCY, NEW_DEVICE, etc."
    ),
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    Retrieve alerts list filtered by status, severity, or alert_type (DISCONNECTED / CONNECTED).
    """
    try:
        return service.get_alerts(
            status=status,
            severity=severity,
            alert_type=alert_type,
            limit=limit
        )
    except Exception as e:
        print(f"GET ALERTS ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts"
        )


@router.get(
    "/summary",
    response_model=AlertsSummary,
    summary="Get alerts summary statistics"
)
def get_alerts_summary():
    """
    Retrieve summary counts: total, active, disconnected, connected, critical, warning, and resolved alerts.
    """
    try:
        return service.get_summary()
    except Exception as e:
        print(f"GET ALERTS SUMMARY ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts summary"
        )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Get specific alert by ID"
)
def get_alert(alert_id: int):
    """
    Retrieve details for a single alert.
    """
    alert = service.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    return alert


@router.post(
    "",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new alert"
)
def create_alert(data: AlertCreate):
    """
    Create a new alert record (DISCONNECTED, CONNECTED, etc.).
    """
    try:
        return service.create_alert(
            device_ip=data.device_ip,
            message=data.message,
            title=data.title,
            device_id=data.device_id,
            device_name=data.device_name,
            alert_type=data.alert_type,
            severity=data.severity
        )
    except Exception as e:
        print(f"CREATE ALERT ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create alert: {str(e)}"
        )


@router.put(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Mark an alert as acknowledged"
)
def acknowledge_alert(alert_id: int):
    """
    Acknowledge an active alert.
    """
    alert = service.acknowledge_alert(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    return alert


@router.put(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Mark an alert as resolved"
)
def resolve_alert(alert_id: int):
    """
    Resolve an active or acknowledged alert.
    """
    alert = service.resolve_alert(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    return alert


@router.delete(
    "/{alert_id}",
    summary="Delete an alert record"
)
def delete_alert(alert_id: int):
    """
    Delete an alert from the database.
    """
    deleted = service.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    return {"message": "Alert deleted successfully"}
