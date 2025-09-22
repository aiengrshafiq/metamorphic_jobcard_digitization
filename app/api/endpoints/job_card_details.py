# app/api/endpoints/job_card_details.py
from fastapi import APIRouter, Depends, HTTPException, Body, Form
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import or_
from typing import List

from app.api import deps
from app import models

router = APIRouter()

# --- NEW ORDER: Static path goes FIRST ---
@router.get("/personnel", tags=["Job Card Details"])
def get_all_personnel(db: Session = Depends(deps.get_db)):
    """Fetches lists of all Supervisors and Foremen."""
    supervisors = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SUPERVISOR).all()
    foremen = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.FOREMAN).all()
    return {"supervisors": supervisors, "foremen": foremen}


# --- Dynamic paths with {jc_id} go AFTER ---
@router.get("/{jc_id}", tags=["Job Card Details"])
def get_job_card_details(
    jc_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Fetches all details for a single Job Card."""
    job_card = db.query(models.JobCard).options(
        joinedload(models.JobCard.project),
        joinedload(models.JobCard.created_by),
        joinedload(models.JobCard.site_engineer_user),
        joinedload(models.JobCard.supervisor_user),
        joinedload(models.JobCard.foreman_user),
        selectinload(models.JobCard.tasks),
        joinedload(models.JobCard.comments).joinedload(models.JobCardComment.comment_by),
        joinedload(models.JobCard.assignment_logs).options(
            joinedload(models.JobCardAssignmentLog.changed_by),
            joinedload(models.JobCardAssignmentLog.assigned_supervisor),
            joinedload(models.JobCardAssignmentLog.assigned_foreman)
        )
    ).filter(models.JobCard.id == jc_id).first()

    if not job_card:
        raise HTTPException(status_code=404, detail="Job Card not found")

    # Security Check
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    user_roles = {role.name.value for role in current_user.roles}
    is_privileged = bool(privileged_roles.intersection(user_roles))
    
    is_assigned = (
        job_card.site_engineer_user_id == current_user.id or
        job_card.supervisor_user_id == current_user.id or
        job_card.foreman_user_id == current_user.id
    )

    if not is_privileged and not is_assigned:
        raise HTTPException(status_code=403, detail="You do not have permission to view this job card")
        
    return job_card


@router.post("/{jc_id}/comments", tags=["Job Card Details"])
def add_job_card_comment(
    jc_id: int,
    comment_text: str = Form(...),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Adds a new comment to a Job Card."""
    new_comment = models.JobCardComment(
        job_card_id=jc_id,
        comment_by_id=current_user.id,
        comment_text=comment_text
    )
    db.add(new_comment)
    db.commit()
    return {"message": "Comment posted successfully"}


@router.post("/{jc_id}/reassign", tags=["Job Card Details"])
def reassign_job_card(
    jc_id: int,
    supervisor_user_id: int = Body(...),
    foreman_user_id: int = Body(...),
    notes: str = Body(None),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Re-assigns a Job Card and creates a history log entry."""
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    user_roles = {role.name.value for role in current_user.roles}
    if not privileged_roles.intersection(user_roles):
        raise HTTPException(status_code=403, detail="Not authorized to re-assign job cards")

    job_card = db.query(models.JobCard).filter(models.JobCard.id == jc_id).first()
    if not job_card:
        raise HTTPException(status_code=404, detail="Job Card not found")

    job_card.supervisor_user_id = supervisor_user_id
    job_card.foreman_user_id = foreman_user_id

    log_entry = models.JobCardAssignmentLog(
        job_card_id=jc_id,
        assigned_supervisor_id=supervisor_user_id,
        assigned_foreman_id=foreman_user_id,
        changed_by_id=current_user.id,
        change_notes=notes
    )
    db.add(log_entry)
    db.commit()

    return {"message": "Job Card successfully re-assigned."}