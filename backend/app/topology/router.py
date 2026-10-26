from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
import ipaddress
import logging

from app.dependencies import get_current_user
from . import service
from .schema import (
    SubnetInfo,
    TopologyGraphResponse,
    TopologySummary
)

router = APIRouter(
    prefix="/topology",
    tags=["Topology"],
    dependencies=[Depends(get_current_user)],
)

logger = logging.getLogger(__name__)


# ==================================================
# DYNAMIC TOPOLOGY GRAPH ENDPOINTS
# ==================================================

@router.get(
    "",
    response_model=TopologyGraphResponse,
    summary="Get topology for registered devices"
)
@router.get(
    "/manual",
    response_model=TopologyGraphResponse,
    summary="Get topology for registered devices"
)
@router.get(
    "/graph",
    response_model=TopologyGraphResponse,
    summary="Get topology for registered devices (alias)"
)
def get_topology_graph(
    refresh_status: bool = Query(
        default=False,
        description="Whether to execute live ping checks on all devices before generating graph"
    ),
    include_wan: bool = Query(
        default=True,
        description="Whether to include WAN/Internet root gateway node in visualization"
    ),
    connected_only: bool = Query(
        default=True,
        description="Whether to only connect and include online/connected devices in the topology graph"
    ),
    source: str = Query(
        default="all",
        pattern="^(all|manual|discovery)$",
        description="Device inventory source: all, manually registered, or discovered"
    ),
    grouping_network: str | None = Query(
        default=None,
        description="Optional CIDR from the latest discovery scan to group matching devices"
    ),
    response: Response = None,
):
    """
    Retrieve registered devices grouped by subnet, inferred connections,
    and topology summary data.
    """
    try:
        if grouping_network:
            ipaddress.ip_network(grouping_network, strict=False)
        if response is not None:
            response.headers["Cache-Control"] = "no-store"
        return service.get_topology_graph(
            refresh_status=refresh_status,
            include_wan=include_wan,
            connected_only=connected_only,
            source=None if source == "all" else source,
            grouping_network=grouping_network,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to generate network topology")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate network topology.",
        ) from e


@router.get("/hidden-devices")
def get_hidden_devices(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.get_hidden_devices()
    except Exception as exc:
        logger.exception("Failed to retrieve topology-hidden devices")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hidden topology devices.",
        ) from exc


def _set_topology_visibility(device_id: int, hidden: bool):
    try:
        return service.set_device_topology_hidden(device_id, hidden)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to update device topology visibility")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update device topology visibility.",
        ) from exc


@router.post("/devices/{device_id}/remove")
def remove_device_from_topology(device_id: int):
    return _set_topology_visibility(device_id, True)


@router.post("/devices/{device_id}/restore")
def restore_device_to_topology(device_id: int):
    return _set_topology_visibility(device_id, False)


@router.post(
    "/refresh",
    response_model=TopologyGraphResponse,
    summary="Force live refresh of device statuses and rebuild topology"
)
def refresh_topology(
    connected_only: bool = Query(
        default=True,
        description="Whether to only connect and include online/connected devices in the topology graph"
    ),
    source: str = Query(
        default="all",
        pattern="^(all|manual|discovery)$",
        description="Device inventory source: all, manually registered, or discovered"
    ),
):
    """
    Triggers concurrent status pinging across all registered devices
    and returns a freshly updated topology graph.
    """
    try:
        return service.get_topology_graph(
            refresh_status=True,
            include_wan=True,
            connected_only=connected_only,
            source=None if source == "all" else source,
        )
    except Exception as e:
        print(f"TOPOLOGY REFRESH ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh topology: {str(e)}"
        )


@router.get(
    "/discovery",
    response_model=TopologyGraphResponse,
    summary="Build topology from devices discovered by a network scan"
)
@router.get(
    "/scanned",
    response_model=TopologyGraphResponse,
    summary="Build topology from devices discovered by a network scan"
)
def get_discovery_topology(
    network: str | None = Query(
        default=None,
        description="CIDR network range (e.g. '192.168.1.0/24'). If omitted, auto-detects local network."
    ),
    auto_register: bool = Query(
        default=False,
        description="Whether to automatically register discovered devices into the database"
    ),
    include_wan: bool = Query(
        default=True,
        description="Whether to include WAN/Internet root gateway node in visualization"
    ),
    response: Response = None,
):
    """
    Discovers all active connected devices on the network and constructs a
    dynamic connected topology graph for discovered connected devices only.
    """
    try:
        if response is not None:
            response.headers["Cache-Control"] = "no-store"
        return service.get_discovery_topology(
            network=network,
            auto_register=auto_register,
            include_wan=include_wan
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to generate discovery topology")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate discovery topology.",
        ) from e


@router.get(
    "/summary",
    response_model=TopologySummary,
    summary="Get network topology summary metrics"
)
def get_topology_summary(
    connected_only: bool = Query(
        default=True,
        description="Whether summary calculates metrics for connected devices only"
    )
):
    """
    Returns aggregate stats: device counts by role, online/offline counts,
    link counts, subnet counts, and network health score percentage.
    """
    try:
        return service.get_topology_summary(connected_only=connected_only)
    except Exception as e:
        print(f"TOPOLOGY SUMMARY ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate topology summary: {str(e)}"
        )


@router.get(
    "/subnets",
    response_model=list[SubnetInfo],
    summary="Get subnets breakdown and device mapping"
)
def get_subnets(
    connected_only: bool = Query(
        default=True,
        description="Whether subnets include connected devices only"
    )
):
    """
    Retrieve network subnets, netmasks, gateways, and associated host device IPs.
    """
    try:
        return service.get_subnets(connected_only=connected_only)
    except Exception as e:
        print(f"TOPOLOGY SUBNETS ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve subnets: {str(e)}"
        )
