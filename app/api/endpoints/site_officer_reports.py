# app/api/endpoints/site_officer_reports.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app import models
from app.utils import generate_sas_url

router = APIRouter()

@router.get("/", tags=["Site Officer Reports"])
def get_all_site_officer_reports(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Fetches a list of Site Officer reports.
    - Privileged users see all reports.
    - Non-privileged users (e.g., Supervisors) see only reports they created.
    """
    query = db.query(models.SiteOfficerReport).options(
        joinedload(models.SiteOfficerReport.job_card).joinedload(models.JobCard.project),
        joinedload(models.SiteOfficerReport.created_by)
    )

    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    user_roles = {role.name for role in current_user.roles}
    is_privileged = bool(privileged_roles.intersection(user_roles))

    if not is_privileged:
        query = query.filter(models.SiteOfficerReport.created_by_id == current_user.id)

    reports = query.order_by(models.SiteOfficerReport.date.desc()).all()
    return reports

@router.get("/{report_id}", tags=["Site Officer Reports"])
def get_site_officer_report_details(
    report_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Fetches all details for a single Site Officer report.
    """
    report = db.query(models.SiteOfficerReport).options(
        joinedload(models.SiteOfficerReport.job_card).joinedload(models.JobCard.project),
        joinedload(models.SiteOfficerReport.created_by),
        joinedload(models.SiteOfficerReport.site_officer_user),
        joinedload(models.SiteOfficerReport.duty_officer_user),
        joinedload(models.SiteOfficerReport.toolbox_videos),
        joinedload(models.SiteOfficerReport.site_images)
    ).filter(models.SiteOfficerReport.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Security check
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    user_roles = {role.name for role in current_user.roles}
    is_privileged = bool(privileged_roles.intersection(user_roles))
    
    if not is_privileged and report.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to view this report")

    # Generate SAS URLs for media files
    for video in report.toolbox_videos:
        video.blob_url = generate_sas_url(video.blob_url)
    for image in report.site_images:
        image.blob_url = generate_sas_url(image.blob_url)
        
    return report