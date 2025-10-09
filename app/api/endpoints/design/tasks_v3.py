# app/api/endpoints/design/tasks_v3.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, conint, HttpUrl
from typing import Optional
from datetime import date
from sqlalchemy.orm import selectinload, joinedload
from app.api import deps
from app import models
from app.design_v3_models import DesignTaskV3,DesignStageV3,StageV3Status,StageV3Name, TaskStatusV3
from datetime import datetime, timezone

class TaskSubmitDataV3(BaseModel):
    file_link: HttpUrl

router = APIRouter()


class TaskAssignmentDataV3(BaseModel):
    owner_id: conint(gt=0)
    due_date: Optional[date] = None

@router.post("/{task_id}/assign", tags=["Design V3 Tasks"])
def assign_design_task_v3(
    task_id: int,
    assignment_data: TaskAssignmentDataV3,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Assigns a V3 task to a user and sets its due date."""
    # Security Check: Ensure only a Design Manager or Lead Designer can assign tasks
    user_roles = {role.name for role in current_user.roles}
    if not {"Design Manager", "Lead Designer"}.intersection(user_roles):
        raise HTTPException(status_code=403, detail="Not authorized to assign tasks.")

    task = db.query(DesignTaskV3).filter(DesignTaskV3.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.owner_id = assignment_data.owner_id
    task.due_date = assignment_data.due_date
    db.commit()
    
    return {"message": "Task assigned successfully."}

@router.post("/{task_id}/submit", tags=["Design V3 Tasks"])
def submit_design_task_v3(
    task_id: int,
    submit_data: TaskSubmitDataV3,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Submits a file link for a V3 task."""
    task = db.query(DesignTaskV3).filter(DesignTaskV3.id == task_id).first()
    if not task or task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Task not found or you are not the owner.")

    task.file_link = str(submit_data.file_link)
    task.status = TaskStatusV3.SUBMITTED
    task.submitted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Task submitted successfully."}

@router.get("/my-tasks", tags=["Design V3 Tasks"])
def get_my_tasks_v3(db: Session = Depends(deps.get_db), current_user: models.User = Depends(deps.get_current_user)):
    tasks = db.query(DesignTaskV3).options(
        joinedload(DesignTaskV3.stage).joinedload(DesignStageV3.project)
    ).filter(
        DesignTaskV3.owner_id == current_user.id,
        DesignTaskV3.status == 'Open'
    ).order_by(DesignTaskV3.due_date.asc()).all()
    return tasks