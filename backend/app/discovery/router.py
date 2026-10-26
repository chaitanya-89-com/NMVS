import ipaddress

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_current_user
from . import service


router = APIRouter(
    prefix="/discovery",
    tags=["Discovery"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/ping/{ip}")
def ping(ip: str, port: int | None = Query(default=None, ge=1, le=65535)):

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid IP address"
        )

    return service.check_device(ip, port)


@router.get("/scan")
def scan(network: str):

    try:
        ipaddress.ip_network(
            network,
            strict=False
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid network address"
        )

    devices = service.discover_network(network)

    return {
        "status": "success",
        "network": network,
        "count": len(devices),
        "devices": devices
    }