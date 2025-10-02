# app/api/endpoints/design/phases.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api import deps
from app import models, design_models
from app.design_models import DesignTaskStatus

router = APIRouter()

@router.post("/{phase_id}/close", tags=["Design Phases"])
def close_phase(
    phase_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Checks if a phase's gate conditions are met and, if so, closes the phase.
    """
    # Security Check: Ensure user is a Design Manager
    user_roles = {role.name for role in current_user.roles}
    if "Design Manager" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized for this action.")

    phase = db.query(design_models.DesignPhase).options(
        selectinload(design_models.DesignPhase.tasks)
    ).filter(design_models.DesignPhase.id == phase_id).first()

    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found.")
    
    if phase.status == "Completed":
        raise HTTPException(status_code=400, detail="This phase is already completed.")

    # --- GATE LOGIC ---
    tasks_by_title = {task.title: task for task in phase.tasks}
    missing_items = []

    if phase.name == design_models.DesignPhaseName.PHASE_2:
        if not tasks_by_title.get("IDR – Minutes", {}).file_link:
            missing_items.append("'IDR – Minutes' link")
        if tasks_by_title.get("Handoff to DC", {}).status != DesignTaskStatus.VERIFIED:
            missing_items.append("'Handoff to DC' task must be Verified by the Document Controller")

    elif phase.name == design_models.DesignPhaseName.PHASE_5:
        if tasks_by_title.get("DM QA Review", {}).status != DesignTaskStatus.DONE:
            missing_items.append("'DM QA Review' must be Approved")
        if not tasks_by_title.get("DC Compile & Release", {}).file_link:
            missing_items.append("'DC Compile & Release' link")

    # Add future gate logic for Phase 4 here if needed

    if missing_items:
        error_detail = "Cannot close phase. Missing requirements: " + ", ".join(missing_items) + "."
        raise HTTPException(status_code=400, detail=error_detail)
        
    # All gates passed, close the phase
    phase.status = "Completed"
    db.commit()
    
    return {"message": f"{phase.name.value} has been successfully completed."}