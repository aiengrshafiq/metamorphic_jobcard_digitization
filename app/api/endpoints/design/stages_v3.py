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
from app.design_v3_models import DesignStageV3,TaskStatusV3, SiteVisitLog, StageV3Status, StageV3Name,DesignTaskV3, QSValidation,MeasurementRequisition,InterdisciplinarySignoff
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
    delivery_datetime: Optional[datetime] = None

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
    
    # --- THIS IS THE FIX ---
    # Manually create the log entry, converting HttpUrl objects to strings
    log_entry = SiteVisitLog(
        stage_id=stage_id,
        meeting_held_at=update_data.meeting_held_at,
        mom_link=str(update_data.mom_link),
        site_photos_link=str(update_data.site_photos_link),
        updated_brief_link=str(update_data.updated_brief_link)
    )
    # -----------------------
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

# @router.post("/{stage_id}/sign-off-tech", tags=["Design V3 Stages"])
# def sign_off_stage_5(stage_id: int, discipline: str = Body(..., embed=True), db: Session = Depends(deps.get_db), current_user: models.User = Depends(deps.get_current_user)):
#     stage = db.query(DesignStageV3).filter_by(id=stage_id, name=StageV3Name.TECH_REVIEW).first()
#     if not stage: raise HTTPException(status_code=404, detail="Stage 5 not found.")

#     new_signoff = InterdisciplinarySignoff(stage_id=stage_id, discipline=discipline, is_approved=True, signed_off_at=datetime.now(timezone.utc), signed_off_by_id=current_user.id)
#     db.add(new_signoff)
#     db.commit()
#     return {"message": f"{discipline} review has been signed off."}




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
        vendor_id=request_data.vendor_id,
        delivery_datetime=request_data.delivery_datetime
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

@router.post("/{stage_id}/sign-off-tech", tags=["Design V3 Stages"])
def sign_off_stage_5(
    stage_id: int,
    discipline: str = Body(..., embed=True),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Logs an interdisciplinary sign-off for a Stage 5 task."""
    stage = db.query(DesignStageV3).filter_by(id=stage_id, name=StageV3Name.TECH_REVIEW).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage 5 not found.")
    
    # Add security check for TE role if needed

    new_signoff = InterdisciplinarySignoff(
        stage_id=stage_id,
        discipline=discipline,
        is_approved=True,
        signed_off_by_id=current_user.id
    )
    db.add(new_signoff)
    db.commit()
    return {"message": f"{discipline} review has been signed off."}


@router.post("/{stage_id}/complete-5", tags=["Design V3 Stages"])
def complete_stage_5(
    stage_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Checks if all Stage 5 signoffs are done, then completes the stage."""
    user_roles = {role.name for role in current_user.roles}
    if not {"Design Manager", "Lead Designer"}.intersection(user_roles):
        raise HTTPException(status_code=403, detail="Not authorized for this action.")

    stage = db.query(DesignStageV3).options(
        selectinload(DesignStageV3.interdisciplinary_signoffs)
    ).filter_by(id=stage_id, name=StageV3Name.TECH_REVIEW).first()

    if not stage:
        raise HTTPException(status_code=404, detail="Stage 5 not found.")

    # Gate Logic: Check if all disciplines are signed off (assuming 3 are required)
    REQUIRED_SIGNOFFS = 3
    if len(stage.interdisciplinary_signoffs) < REQUIRED_SIGNOFFS:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot complete stage: Not all technical disciplines have been signed off."
        )
            
    stage.status = StageV3Status.COMPLETED
    _unlock_next_stage(db, stage) # This unlocks Stage 6
    db.commit()
    return {"message": "Stage 5 completed. Authority Drawing Package is now unlocked."}


@router.post("/{stage_id}/complete-6", tags=["Design V3 Stages"])
def complete_stage_6(
    stage_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Checks if all tasks in Stage 6 are submitted, then completes the stage."""
    user_roles = {role.name for role in current_user.roles}
    if not {"Design Manager", "Lead Designer"}.intersection(user_roles):
        raise HTTPException(status_code=403, detail="Not authorized for this action.")

    stage = db.query(DesignStageV3).options(
        selectinload(DesignStageV3.tasks)
    ).filter_by(id=stage_id, name=StageV3Name.AUTHORITY_PACKAGE).first()

    if not stage:
        raise HTTPException(status_code=404, detail="Stage 6 not found.")

    # Gate Logic: Check if all tasks in this stage are Submitted
    for task in stage.tasks:
        if task.status != TaskStatusV3.SUBMITTED:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot complete stage: Task '{task.title}' is not yet submitted."
            )
            
    stage.status = StageV3Status.COMPLETED
    _unlock_next_stage(db, stage) # This unlocks Stage 7
    db.commit()
    return {"message": "Stage 6 completed. Final Package Delivery is now unlocked."}


@router.post("/{stage_id}/complete-7", tags=["Design V3 Stages"])
def complete_stage_7(
    stage_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Checks if all tasks in Stage 7 are submitted, then completes the stage."""
    user_roles = {role.name for role in current_user.roles}
    if not {"Design Manager", "Lead Designer"}.intersection(user_roles):
        raise HTTPException(status_code=403, detail="Not authorized for this action.")

    stage = db.query(DesignStageV3).options(
        selectinload(DesignStageV3.tasks)
    ).filter_by(id=stage_id, name=StageV3Name.FINAL_DELIVERY).first()

    if not stage:
        raise HTTPException(status_code=404, detail="Stage 7 not found.")

    # Gate Logic: Check if all tasks in this stage are Submitted
    for task in stage.tasks:
        if task.status != TaskStatusV3.SUBMITTED:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot complete stage: Task '{task.title}' is not yet submitted."
            )
            
    stage.status = StageV3Status.COMPLETED
    _unlock_next_stage(db, stage) # This unlocks Stage 8
    db.commit()
    return {"message": "Stage 7 completed. Handover to Execution is now unlocked."}


@router.post("/{stage_id}/handover-signoff", tags=["Design V3 Stages"])
def handover_stage_8(
    stage_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Handles the dual sign-off for project handover (Stage 8)."""
    stage = db.query(DesignStageV3).options(
        joinedload(DesignStageV3.project)
    ).filter_by(id=stage_id, name=StageV3Name.EXECUTION_HANDOVER).first()
    
    if not stage:
        raise HTTPException(status_code=404, detail="Stage 8 not found.")

    project = stage.project
    user_roles = {role.name for role in current_user.roles}
    signed = False

    if "Design Manager" in user_roles:
        project.handover_design_head_signed_by_id = current_user.id
        project.handover_design_head_signed_at = datetime.now(timezone.utc)
        signed = True
    elif "Operation Manager" in user_roles:
        project.handover_ops_head_signed_by_id = current_user.id
        project.handover_ops_head_signed_at = datetime.now(timezone.utc)
        signed = True
        
    if not signed:
        raise HTTPException(status_code=403, detail="Not authorized for handover sign-off.")
    
    # If both have now signed off, complete the stage and the project
    if project.handover_design_head_signed_by_id and project.handover_ops_head_signed_by_id:
        stage.status = StageV3Status.COMPLETED
        project.status = "Handed Over"

    db.commit()
    return {"message": "Handover successfully signed."}