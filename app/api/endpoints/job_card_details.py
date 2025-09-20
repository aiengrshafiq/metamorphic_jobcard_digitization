# app/api/endpoints/job_card_details.py
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import or_

from app.api import deps
from app import models

router = APIRouter()

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
        joinedload(models.JobCard.comments).joinedload(models.JobCardComment.comment_by)
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
    # The frontend will re-fetch the list, so we can just return a success message
    return {"message": "Comment posted successfully"}