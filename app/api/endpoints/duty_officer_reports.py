# app/api/endpoints/duty_officer_reports.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app import models
from app.utils import generate_sas_url

router = APIRouter()

@router.get("/", tags=["Duty Officer Reports"])
def get_all_duty_officer_reports(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Fetches a list of Duty Officer Progress reports.
    - Privileged users see all reports.
    - Non-privileged users (e.g., Foremen) see only reports they created.
    """
    # Base query with eager loading for performance on the list page
    query = db.query(models.DutyOfficerProgress).options(
        joinedload(models.DutyOfficerProgress.job_card).joinedload(models.JobCard.project),
        joinedload(models.DutyOfficerProgress.created_by)
    )

    # Define roles that can see ALL reports
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    user_roles = {role.name.value for role in current_user.roles}
    is_privileged = bool(privileged_roles.intersection(user_roles))

    # If the user is NOT privileged, filter the query to their own records
    if not is_privileged:
        query = query.filter(models.DutyOfficerProgress.created_by_id == current_user.id)

    reports = query.order_by(models.DutyOfficerProgress.date_of_work.desc()).all()
    return reports

@router.get("/{report_id}", tags=["Duty Officer Reports"])
def get_duty_officer_report_details(
    report_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Fetches all details for a single Duty Officer Progress report.
    """
    report = db.query(models.DutyOfficerProgress).options(
        joinedload(models.DutyOfficerProgress.job_card).joinedload(models.JobCard.project),
        joinedload(models.DutyOfficerProgress.created_by),
        joinedload(models.DutyOfficerProgress.foreman_signature),
        joinedload(models.DutyOfficerProgress.toolbox_videos),
        joinedload(models.DutyOfficerProgress.site_images)
    ).filter(models.DutyOfficerProgress.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Security check: Ensure non-privileged users can only see their own reports
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    user_roles = {role.name.value for role in current_user.roles}
    is_privileged = bool(privileged_roles.intersection(user_roles))
    
    if not is_privileged and report.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to view this report")

    # Generate SAS URLs for media files
    for video in report.toolbox_videos:
        video.blob_url = generate_sas_url(video.blob_url)
    for image in report.site_images:
        image.blob_url = generate_sas_url(image.blob_url)
        
    return report