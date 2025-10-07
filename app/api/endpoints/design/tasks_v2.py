# app/api/endpoints/design/tasks_v2.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, conint, HttpUrl
from typing import Optional
from datetime import date, datetime, timezone

from app.api import deps
from app import models
from app.design_v2_models import DesignTaskV2, TaskStatusV2

router = APIRouter()

class TaskAssignmentDataV2(BaseModel):
    owner_id: conint(gt=0)
    due_date: Optional[date] = None

class TaskSubmitDataV2(BaseModel):
    file_link: HttpUrl

@router.post("/{task_id}/assign", tags=["Design V2 Tasks"])
def assign_design_task_v2(
    task_id: int,
    assignment_data: TaskAssignmentDataV2,
    db: Session = Depends(deps.get_db)
):
    """Assigns a V2 task to a user and sets its due date."""
    task = db.query(DesignTaskV2).filter(DesignTaskV2.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.owner_id = assignment_data.owner_id
    task.due_date = assignment_data.due_date
    db.commit()
    
    return {"message": "Task assigned successfully."}


@router.post("/{task_id}/submit", tags=["Design V2 Tasks"])
def submit_design_task_v2(
    task_id: int,
    submit_data: TaskSubmitDataV2,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Submits a file link for a V2 task."""
    task = db.query(DesignTaskV2).filter(DesignTaskV2.id == task_id).first()
    if not task or task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Task not found or you are not the owner.")

    task.file_link = str(submit_data.file_link)
    task.status = TaskStatusV2.SUBMITTED
    task.submitted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Task submitted successfully."}