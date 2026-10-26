
import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError

from app.monitoring import service as monitoring_service
from app.speed_monitoring import service as speed_service
from .schema import AgentScanResults, AgentSpeedTestClaim, AgentSpeedTestResult

agent_bearer = HTTPBearer(auto_error=False)

router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)


def verify_agent_token(
    authorization: str | None = None,
):
    expected_token = os.getenv("NMVS_AGENT_TOKEN", "").strip()

    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent authentication is not configured",
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    scheme, separator, supplied_token = authorization.partition(" ")

    if (
        scheme.lower() != "bearer"
        or not separator
        or not supplied_token.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization must use Bearer token format",
        )

    if not hmac.compare_digest(
        supplied_token.strip(),
        expected_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent token does not match",
        )


@router.get("/health")
def agent_health():
    return {
        "status": "ok",
        "message": "NMVS Agent API is ready",
    }


@router.post("/scan-results")
def receive_scan_results(
    data: AgentScanResults,
    credentials: HTTPAuthorizationCredentials | None = Depends(agent_bearer),
):
    authorization = (
        f"{credentials.scheme} {credentials.credentials}"
        if credentials is not None
        else None
    )
    verify_agent_token(authorization)

    try:
        result = monitoring_service.save_agent_scan_results(
            data.devices,
            network=data.network,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save agent scan results",
        ) from exc

    return {
        "message": "Scan results processed",
        "received": len(data.devices),
        **result,
    }


@router.post("/speed-tests/claim")
def claim_speed_test(
    data: AgentSpeedTestClaim,
    credentials: HTTPAuthorizationCredentials | None = Depends(agent_bearer),
):
    verify_agent_token(
        f"{credentials.scheme} {credentials.credentials}"
        if credentials is not None
        else None
    )
    try:
        return {"job": speed_service.claim_device_test([str(ip) for ip in data.local_ips])}
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to claim a device speed test",
        ) from exc


@router.post("/speed-tests/{job_id}/complete")
def complete_speed_test(
    job_id: int,
    data: AgentSpeedTestResult,
    credentials: HTTPAuthorizationCredentials | None = Depends(agent_bearer),
):
    verify_agent_token(
        f"{credentials.scheme} {credentials.credentials}"
        if credentials is not None
        else None
    )
    try:
        return speed_service.complete_device_test(
            job_id=job_id,
            ip=str(data.ip),
            download_mbps=data.download_mbps,
            upload_mbps=data.upload_mbps,
            ping_ms=data.ping_ms,
            error=data.error,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save device speed test results",
        ) from exc
