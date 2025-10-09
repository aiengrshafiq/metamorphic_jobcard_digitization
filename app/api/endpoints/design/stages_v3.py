# app/api/endpoints/design/stages_v3.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime, timezone
from fastapi import Request
from app.api import deps
from app import models, schemas
from sqlalchemy.orm import selectinload, joinedload
from app.design_v3_models import DesignStageV3,TaskStatusV3, SiteVisitLog, StageV3Status, StageV3Name,DesignTaskV3, QSValidation,MeasurementRequisition
from fastapi.responses import HTMLResponse


from fastapi.responses import HTMLResponse # Add this import
from fastapi.templating import Jinja2Templates # Add this import

# Add this at the top, after your router definition
templates = Jinja2Templates(directory="templates")

router = APIRouter()

class SiteVisitUpdate(BaseModel):
    meeting_held_at: datetime
    mom_link: HttpUrl
    site_photos_link: HttpUrl
    updated_brief_link: HttpUrl

class MeasurementRequestCreate(BaseModel):
    vendor_id: int

class MeasurementComplete(BaseModel):
    measurement_package_link: HttpUrl

class QSUpdate(BaseModel):
    cost_estimation_sheet_link: HttpUrl
    validated_boq_link: HttpUrl

def _unlock_next_stage(db: Session, current_stage: DesignStageV3):
    next_stage = db.query(DesignStageV3).filter_by(project_id=current_stage.project_id, order=current_stage.order + 1).first()
    if next_stage:
        next_stage.status = StageV3Status.IN_PROGRESS

@router.post("/{stage_id}/complete-2a", tags=["Design V3 Stages"])
def complete_stage_2a(stage_id: int, update_data: SiteVisitUpdate, db: Session = Depends(deps.get_db)):
    stage = db.query(DesignStageV3).filter_by(id=stage_id, name=StageV3Name.SITE_VISIT, status=StageV3Status.IN_PROGRESS).first()
    if not stage: raise HTTPException(status_code=404, detail="Active Stage 2A not found.")
    
    log_entry = SiteVisitLog(stage_id=stage_id, **update_data.dict())
    db.add(log_entry)
    stage.status = StageV3Status.COMPLETED
    _unlock_next_stage(db, stage)
    db.commit()
    return {"message": "Stage 2A completed."}

@router.post("/{stage_id}/complete-4", tags=["Design V3 Stages"])
def complete_stage_4_qs(
    stage_id: int,
    update_data: QSUpdate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Completes Stage 4, logs the QS validation, and unlocks the next stage."""
    stage = db.query(DesignStageV3).filter_by(id=stage_id, name=StageV3Name.QS_HANDOVER, status=StageV3Status.IN_PROGRESS).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Active Stage 4 (QS Handover) not found.")

    log_entry = QSValidation(
        stage_id=stage_id,
        validated_by_id=current_user.id,
        cost_estimation_sheet_link=str(update_data.cost_estimation_sheet_link),
        validated_boq_link=str(update_data.validated_boq_link)
    )
    db.add(log_entry)
    
    stage.status = StageV3Status.COMPLETED
    _unlock_next_stage(db, stage) # Re-use the helper to unlock Stage 5
    
    db.commit()
    return {"message": "Stage 4 (QS) completed successfully."}

@router.post("/{stage_id}/sign-off-tech", tags=["Design V3 Stages"])
def sign_off_stage_5(stage_id: int, discipline: str = Body(..., embed=True), db: Session = Depends(deps.get_db), current_user: models.User = Depends(deps.get_current_user)):
    stage = db.query(DesignStageV3).filter_by(id=stage_id, name=StageV3Name.TECH_REVIEW).first()
    if not stage: raise HTTPException(status_code=404, detail="Stage 5 not found.")

    new_signoff = InterdisciplinarySignoff(stage_id=stage_id, discipline=discipline, is_approved=True, signed_off_at=datetime.now(timezone.utc), signed_off_by_id=current_user.id)
    db.add(new_signoff)
    db.commit()
    return {"message": f"{discipline} review has been signed off."}




@router.post("/{stage_id}/create-measurement-req", tags=["Design V3 Stages"])
def create_measurement_requisition(
    stage_id: int,
    request_data: MeasurementRequestCreate,
    db: Session = Depends(deps.get_db)
):
    stage = db.query(DesignStageV3).filter_by(id=stage_id, name=StageV3Name.MEASUREMENT, status=StageV3Status.IN_PROGRESS).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Active Stage 2B not found.")
    if stage.measurement_requisition:
        raise HTTPException(status_code=400, detail="A measurement request already exists for this stage.")

    new_req = MeasurementRequisition(
        stage_id=stage_id,
        vendor_id=request_data.vendor_id
    )
    db.add(new_req)
    db.commit()
    # In a real-world scenario, you would trigger an email to the vendor here.
    return {"message": f"Measurement request sent to vendor."}



@router.get("/{stage_id}/tasks-html", response_class=HTMLResponse, tags=["Design V3 Stages"])
def get_stage_tasks_html(
    stage_id: int,
    request: Request, # Add the request object
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Renders the HTML partial for a task-based stage."""
    stage = db.query(DesignStageV3).options(
        selectinload(DesignStageV3.tasks).joinedload(DesignTaskV3.owner)
    ).filter(DesignStageV3.id == stage_id).first()

    if not stage:
        return "<p class='text-danger p-3'>Stage not found.</p>"
        
    # Fetch team members for the assignment dropdown
    team_roles = [models.UserRole.DESIGN_TEAM_MEMBER, models.UserRole.LEAD_DESIGNER, models.UserRole.TECH_ENGINEER, models.UserRole.DOC_CONTROLLER, models.UserRole.DESIGN_MANAGER]
    team_members = db.query(models.User).join(models.User.roles).filter(models.Role.name.in_(team_roles)).all()
    
    # Prepare context for the template
    context = {
        "request": request,
        "stage": stage,
        "team_members": team_members,
        "user": current_user,
        "user_roles": {role.name for role in current_user.roles}
    }
    return templates.TemplateResponse("design/v3/_stage_task_list.html", context)



@router.post("/{stage_id}/complete-2b", tags=["Design V3 Stages"])
def complete_stage_2b(
    stage_id: int,
    update_data: MeasurementComplete,
    db: Session = Depends(deps.get_db)
):
    """Marks Stage 2B as complete and unlocks the next stage."""
    stage = db.query(DesignStageV3).filter_by(id=stage_id, name=StageV3Name.MEASUREMENT).first()
    if not stage or not stage.measurement_requisition:
        raise HTTPException(status_code=404, detail="Active measurement requisition not found.")

    # Update the measurement requisition record
    stage.measurement_requisition.status = "Approved"
    stage.measurement_requisition.measurement_package_link = str(update_data.measurement_package_link)
    
    # Gate Logic: Complete Stage 2B and unlock Stage 3
    stage.status = StageV3Status.COMPLETED
    _unlock_next_stage(db, stage)
    
    db.commit()
    return {"message": "Measurement received and Stage 2B is complete."}




@router.post("/{stage_id}/complete-3", tags=["Design V3 Stages"])
def complete_stage_3(
    stage_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Checks if all tasks in Stage 3 are submitted, then completes the stage."""
    user_roles = {role.name for role in current_user.roles}
    if not {"Design Manager", "Lead Designer"}.intersection(user_roles):
        raise HTTPException(status_code=403, detail="Not authorized.")

    stage = db.query(DesignStageV3).options(selectinload(DesignStageV3.tasks)).filter_by(id=stage_id).first()
    if not stage or stage.name != StageV3Name.INITIAL_DESIGN:
        raise HTTPException(status_code=404, detail="Stage 3 not found.")

    for task in stage.tasks:
        if task.status != TaskStatusV3.SUBMITTED:
            raise HTTPException(status_code=400, detail=f"Cannot complete: Task '{task.title}' is not submitted.")
            
    stage.status = StageV3Status.COMPLETED
    _unlock_next_stage(db, stage)
    db.commit()
    return {"message": "Stage 3 completed. Handoff to QS initiated."}