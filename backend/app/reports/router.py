from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies import get_current_user
from app.timezone import now_ist
from . import service

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/devices/csv",
    summary="Download device inventory as CSV",
    response_class=Response
)
def download_devices_csv():
    """Download registered devices inventory report in CSV format."""
    try:
        csv_content = service.get_devices_report_csv()
        filename = f"devices_report_{now_ist().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"DEVICES CSV ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate devices CSV report"
        )


@router.get(
    "/executive/pdf",
    summary="Download complete executive network health PDF report",
    response_class=Response
)
def download_executive_summary_pdf():
    """Download comprehensive executive network health report in PDF format."""
    try:
        pdf_bytes = service.get_executive_summary_pdf()
        filename = f"executive_summary_{now_ist().strftime('%Y%m%d_%H%M%S')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"EXECUTIVE SUMMARY ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate executive summary report"
        )
