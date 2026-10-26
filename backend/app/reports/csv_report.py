import csv
import io

from app.timezone import as_ist


def generate_devices_csv(devices: list) -> str:
    """Generate CSV string of network devices inventory."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Device ID",
        "Name",
        "IP Address",
        "Device Type",
        "Network Type",
        "Source",
        "Registered At (IST)",
        "Updated At (IST)",
    ])

    for d in devices:
        writer.writerow([
            d.id,
            d.name,
            d.ip,
            d.device_type,
            getattr(d, "network_type", "Unknown") or "Unknown",
            getattr(d, "source", "manual") or "manual",
            as_ist(d.created_at).isoformat() if getattr(d, "created_at", None) else "N/A",
            as_ist(d.updated_at).isoformat() if getattr(d, "updated_at", None) else "N/A",
        ])

    return output.getvalue()
