from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_token_header

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)

from ..models.reports import ReportControlRequest, ReportDriversRequest
from ..services.reports import (
    fetch_trucks_control,
    fetch_vehicle_control,
    fetch_order_information,
    fetch_loading_distribution,
    fetch_loading_distribution_interval,
    fetch_load_report_driver_by_month,
)

@router.post("/control/")
async def get_control_report(request: ReportControlRequest):
    """
    Generates a control report and sends it to the specified emails.
    - **date_ref**: Optional reference date (format: YYYY-MM-DD).
    - **start_date**: Optional start date for a date range.
    - **end_date**: Optional end date for a date range.
    - **emails**: List of emails to send the report to.
    """
    if request.date_ref:
        # Logic for a single date
        fetch_trucks_control(request.date_ref, request.emails)
        fetch_vehicle_control(request.date_ref, request.emails)
        fetch_order_information(request.date_ref, request.emails)
        result = fetch_loading_distribution(request.date_ref, request.emails)
    elif request.start_date and request.end_date:
        # Logic for a date range
        result = fetch_loading_distribution_interval(
            request.start_date, request.end_date, request.emails
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'date_ref' or both 'start_date' and 'end_date' must be provided.",
        )
    return result


@router.post("/drivers_incentives/")
async def get_drivers_incentives_report(request: ReportDriversRequest):
    """
    Generates a report on driver incentives for a given year and month.
    - **year_ref**: The reference year.
    - **month_ref**: The reference month.
    - **emails**: List of emails to send the report to.
    """
    result = fetch_load_report_driver_by_month(
        request.year_ref, request.month_ref, request.emails
    )
    return result

