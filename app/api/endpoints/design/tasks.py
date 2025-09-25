# app/api/endpoints/design/tasks.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone
from pydantic import Field
from pydantic import BaseModel
from typing import Optional, List

from app.api import deps
from app import models, design_models
from app.design_models import DesignTaskStatus

router = APIRouter()

# CORRECTED: The path is now "/me"
@router.get("/me", tags=["My Tasks"])
def get_my_tasks(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Fetches all active tasks assigned to the current user."""
    tasks = db.query(design_models.DesignTask).options(
        joinedload(design_models.DesignTask.phase).joinedload(design_models.DesignPhase.project)
    ).filter(
        design_models.DesignTask.owner_id == current_user.id,
        design_models.DesignTask.status.in_([DesignTaskStatus.OPEN, DesignTaskStatus.REVISION_REQUESTED])
    ).order_by(design_models.DesignTask.due_date.asc()).all()
    return tasks

# The POST endpoint is correct as is, no changes needed to its logic.
@router.post("/{task_id}/submit", tags=["My Tasks"])
def submit_task(
    task_id: int,
    file_link: str = Body(..., embed=True),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Submits a file link for a task, updates its status, and calculates its score."""
    task = db.query(design_models.DesignTask).filter(design_models.DesignTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    if task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not authorized to submit this task.")

    task.file_link = file_link
    task.status = DesignTaskStatus.SUBMITTED
    task.submitted_at = datetime.now(timezone.utc)
    
    lateness_days = 0
    if task.due_date and task.submitted_at.date() > task.due_date:
        lateness_days = (task.submitted_at.date() - task.due_date).days
    
    late_penalty = 10 * ((lateness_days + 1) // 2)
    final_score = max(0, 100 - late_penalty)

    score_record = db.query(design_models.DesignScore).filter(design_models.DesignScore.task_id == task_id).first()
    if score_record:
        score_record.score = final_score
        score_record.lateness_days = lateness_days
    else:
        new_score = design_models.DesignScore(
            task_id=task_id,
            score=final_score,
            lateness_days=lateness_days
        )
        db.add(new_score)

    db.commit()
    return {"message": "Task submitted successfully!", "score": final_score}


class TaskReviewData(BaseModel):
    status: DesignTaskStatus
    notes: Optional[str] = None

@router.post("/{task_id}/review", tags=["My Tasks"])
def review_task(
    task_id: int,
    review_data: TaskReviewData,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Allows a user with appropriate permissions to review a task."""
    user_roles = {role.name.value for role in current_user.roles}
    if "Design Manager" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized to review tasks.")

    task = db.query(design_models.DesignTask).options(
        joinedload(design_models.DesignTask.score)
    ).filter(design_models.DesignTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    task.status = review_data.status # e.g., DONE or REVISION_REQUESTED
    
    # Apply a penalty if a revision is requested
    if review_data.status == DesignTaskStatus.REVISION_REQUESTED:
        if task.score:
            # Simple 10-point penalty for a revision
            task.score.score = max(0, task.score.score - 10)
    
    # Here you could also add logic to create a new comment with the review notes
    if review_data.notes:
        comment = design_models.DesignTaskComment(
            task_id=task_id,
            comment_by_id=current_user.id,
            comment_text=f"QA Note: {review_data.notes}"
        )
        db.add(comment)

    db.commit()
    return {"message": f"Task status updated to {review_data.status.value}"}