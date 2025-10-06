# app/api/endpoints/design/tasks.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone
from pydantic import Field
from pydantic import BaseModel
from typing import Optional, List
from fastapi import BackgroundTasks

from app.api import deps
from app import models, design_models
from app.design_models import DesignTaskStatus
from app.services.slack import send_design_slack_notification # 2. Import the slack service
from app.core.config import settings # 3. Import settings for the BASE_URL

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
    background_tasks: BackgroundTasks,
    file_link: Optional[str] = Body(None, embed=True),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Submits a file link for a task, updates its status, and calculates its score."""
    task = db.query(design_models.DesignTask).filter(design_models.DesignTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    if task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not authorized to submit this task.")

    if task.title != "Ready for QA" and not file_link:
        raise HTTPException(status_code=400, detail="A file link is required to submit this task.")

    task.file_link = file_link
    task.status = DesignTaskStatus.SUBMITTED
    task.submitted_at = datetime.now(timezone.utc)

    # --- ADD/UPDATE NOTIFICATION LOGIC ---
    notification_message = ""
    project_name = task.phase.project.name
    task_link = f"<{settings.BASE_URL}/design/projects/{task.phase.project.id}|View Project>"


    # --- NEW TRIGGER LOGIC ---
    # 2. If this is the "Ready for QA" task, trigger the "DM QA Review" task
    if task.title == "Ready for QA":
        qa_review_task = db.query(design_models.DesignTask).filter(
            design_models.DesignTask.phase_id == task.phase_id,
            design_models.DesignTask.title == "DM QA Review"
        ).first()
        if qa_review_task and qa_review_task.status == DesignTaskStatus.OPEN:
            qa_review_task.status = DesignTaskStatus.SUBMITTED
            notification_message = f"✅ *Ready for Review:* `{project_name}` is ready for DM QA Review. {task_link}"
    # -------------------------
     # --- ADD THIS TRIGGER LOGIC ---
    # If the submitted task is "Technical Drawings", find the sibling "Engineer Sign-off"
    # task in the same phase and set its status to "Submitted".
    if task.title == "Technical Drawings":
        sign_off_task = db.query(design_models.DesignTask).filter(
            design_models.DesignTask.phase_id == task.phase_id,
            design_models.DesignTask.title == "Engineer Sign-off"
        ).first()
        if sign_off_task and sign_off_task.status == DesignTaskStatus.OPEN:
            sign_off_task.status = DesignTaskStatus.SUBMITTED
            notification_message = f"📐 *Ready for Sign-off:* `{project_name}` has technical drawings ready for sign-off. {task_link}"
    # --------------------------------

    if notification_message:
        background_tasks.add_task(
            send_design_slack_notification, 
            message=notification_message
        )
    
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
    user_roles = {role.name for role in current_user.roles}
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


@router.post("/{task_id}/verify", tags=["My Tasks"])
def verify_task(
    task_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Allows a Document Controller to verify a submitted task."""
    user_roles = {role.name for role in current_user.roles}
    if "Document Controller" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized for this action.")

    task = db.query(design_models.DesignTask).filter(design_models.DesignTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.status != DesignTaskStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Task must be in 'Submitted' state to be verified.")

    task.status = DesignTaskStatus.VERIFIED
    task.verified_at = datetime.now(timezone.utc)
    task.verified_by_id = current_user.id
    
    db.commit()
    return {"message": "Task has been verified successfully."}


# Below is TE sign-off endpoint
class TaskSignOffData(BaseModel):
    notes: Optional[str] = None

@router.post("/{task_id}/sign-off", tags=["My Tasks"])
def sign_off_task(
    task_id: int,
    sign_off_data: TaskSignOffData,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Allows a Technical Engineer to sign off on a task."""
    user_roles = {role.name for role in current_user.roles}
    if "Technical Engineer" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized for this action.")

    task = db.query(design_models.DesignTask).filter(design_models.DesignTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.status != DesignTaskStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Task must be in 'Submitted' state for sign-off.")

    task.status = DesignTaskStatus.VERIFIED # A sign-off is a form of verification
    task.signed_off_at = datetime.now(timezone.utc)
    task.signed_off_by_id = current_user.id
    task.sign_off_notes = sign_off_data.notes
    
    db.commit()
    return {"message": "Task has been signed off successfully."}


# Add this Pydantic model for comment validation
class CommentCreate(BaseModel):
    comment_text: str

# Add these two new endpoints to the file
@router.get("/{task_id}", tags=["My Tasks"])
def get_task_details(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """Fetches all details for a single Design Task."""
    task = db.query(design_models.DesignTask).options(
        joinedload(design_models.DesignTask.phase).joinedload(design_models.DesignPhase.project),
        joinedload(design_models.DesignTask.owner),
        joinedload(design_models.DesignTask.comments).joinedload(design_models.DesignTaskComment.comment_by)
    ).filter(design_models.DesignTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task

@router.post("/{task_id}/comments", tags=["My Tasks"])
def add_task_comment(
    task_id: int,
    comment: CommentCreate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Adds a new comment to a Design Task."""
    new_comment = design_models.DesignTaskComment(
        task_id=task_id,
        comment_by_id=current_user.id,
        comment_text=comment.comment_text
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment