
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from . import service
from .schema import (
    DeviceCreate,
    DeviceDetectResponse,
    DeviceResponse,
    DeviceUpdate,
)
from .detector import detect_network_provider


router = APIRouter(
    prefix="/devices",
    tags=["Devices"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/network-provider")
def get_network_provider():
    """Detect the ISP associated with the backend's public IP."""
    result = detect_network_provider()

    if result.get("isp") == "Unknown":
        raise HTTPException(
            status_code=502,
            detail="Unable to identify the network provider",
        )

    return result


@router.get("/detect/{ip}", response_model=DeviceDetectResponse)
def detect_device(ip: str):
    try:
        return service.detect_ip(ip)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        print(f"DETECT DEVICE ERROR: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to detect device",
        )


@router.post(
    "/",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_device(data: DeviceCreate):
    try:
        device = service.create_device(
            name=data.name,
            ip=str(data.ip),
            network_type=data.network_type,
            service_port=data.service_port,
            health_check_url=data.health_check_url,
        )
        return device
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        print(f"CREATE DEVICE ERROR: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create device",
        )


@router.get("/", response_model=list[DeviceResponse])
def get_devices():
    try:
        return service.get_devices()
    except Exception as exc:
        print(f"GET DEVICES ERROR: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get devices",
        )


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int):
    device = service.get_device(device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    return device


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(device_id: int, data: DeviceUpdate):
    try:
        device = service.update_device(
            device_id=device_id,
            name=data.name,
            ip=str(data.ip) if data.ip is not None else None,
            network_type=data.network_type,
            service_port=data.service_port,
            health_check_url=data.health_check_url,
            update_service_port="service_port" in data.model_fields_set,
            update_health_check_url="health_check_url" in data.model_fields_set,
        )

        if device is None:
            raise HTTPException(
                status_code=404,
                detail="Device not found",
            )

        return device

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        print(f"UPDATE DEVICE ERROR: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update device",
        )


@router.delete("/{device_id}")
def delete_device(device_id: int):
    try:
        result = service.delete_device(device_id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Device not found",
            )

        return {"message": "Device deleted successfully"}

    except HTTPException:
        raise
    except Exception as exc:
        print(f"DELETE DEVICE ERROR: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete device",
        )


@router.post("/{device_id}/redetect", response_model=DeviceResponse)
def redetect_device(device_id: int):
    try:
        device = service.redetect_device(device_id)

        if device is None:
            raise HTTPException(
                status_code=404,
                detail="Device not found",
            )

        return device

    except HTTPException:
        raise
    except Exception as exc:
        print(f"REDETECT DEVICE ERROR: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Failed to re-detect device type",
        )
