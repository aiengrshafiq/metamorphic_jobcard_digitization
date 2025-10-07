# app/api/endpoints/design/projects_v2.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.api import deps
from app import models
from app.design_v2_models import DesignProjectV2, DesignStage, DesignTaskV2, StageName, StageStatus, TaskStatusV2



from sqlalchemy.orm import selectinload # Add this import
from sqlalchemy.orm import joinedload

router = APIRouter()

# The full list of deliverables for V2
DELIVERABLE_TEMPLATES_V2 = {
    StageName.STAGE_2A: ["Site Visit & Client Meeting"],
    StageName.STAGE_3: ["2D Layout", "SketchUp Model", "Render Set v1", "Preliminary BOQ"],
    StageName.STAGE_5: ["Structural Review", "MEP Review", "Landscape Review"],
    StageName.STAGE_6: ["Architectural Set", "Structural Set", "MEP Set", "Landscape Set", "Lighting Set", "Paint Plans Set"],
    # Other stages have actions, not deliverables
}

class ProjectCreateV2(BaseModel):
    name: str
    client: str

@router.post("/", tags=["Design V2"])
def create_design_project_v2(
    project_data: ProjectCreateV2,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Creates a new V2 Design Project and all its stages and default tasks."""
    try:
        new_project = DesignProjectV2(
            name=project_data.name,
            client=project_data.client,
            created_by_id=current_user.id
        )
        db.add(new_project)
        db.flush()

        # Create all 8 stages in order
        for i, stage_enum in enumerate(StageName):
            stage_status = StageStatus.IN_PROGRESS if i == 0 else StageStatus.LOCKED
            new_stage = DesignStage(
                project_id=new_project.id,
                name=stage_enum,
                status=stage_status,
                order=i + 1
            )
            db.add(new_stage)
            db.flush()
            
            # Create the default tasks for this stage
            tasks_for_stage = DELIVERABLE_TEMPLATES_V2.get(stage_enum, [])
            for task_title in tasks_for_stage:
                new_task = DesignTaskV2(
                    stage_id=new_stage.id,
                    title=task_title,
                    status=TaskStatusV2.OPEN
                )
                db.add(new_task)

        db.commit()
        return {"message": "Design project (V2) created successfully!", "project_id": new_project.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")



# Add this new function to the file
@router.get("/{project_id}", tags=["Design V2"])
def get_design_project_v2_details(project_id: int, db: Session = Depends(deps.get_db)):
    """Fetches a single V2 Design Project with all its stages, tasks, and compliance data."""
    project = db.query(DesignProjectV2).options(
        selectinload(DesignProjectV2.stages).options(
            selectinload(DesignStage.tasks).joinedload(DesignTaskV2.owner),
            selectinload(DesignStage.site_visit_log), # Eager load new compliance models
            selectinload(DesignStage.interdisciplinary_signoffs).joinedload(models.User)
        )
    ).filter(DesignProjectV2.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Design project not found")
    
    return project


# --- ADD THIS NEW ENDPOINT ---
@router.get("/", tags=["Design V2"])
def get_design_projects_v2(
    db: Session = Depends(deps.get_db)
):
    """Fetches a list of all V2 Design Projects."""
    projects = db.query(DesignProjectV2).options(
        joinedload(DesignProjectV2.created_by)
    ).order_by(DesignProjectV2.id.desc()).all()
    return projects
# -----------------------------

@router.post("/{project_id}/handover", tags=["Design V2"])
def handover_project_v2(
    project_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Handles the dual sign-off for project handover (Stage 8)."""
    project = db.query(DesignProjectV2).filter_by(id=project_id).first()
    user_roles = {role.name.value for role in current_user.roles}

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if "Design Manager" in user_roles:
        project.handover_design_head_signed_by_id = current_user.id
        project.handover_design_head_signed_at = datetime.now(timezone.utc)
    elif "Operation Manager" in user_roles: # Assuming 'Operation Manager' is the Ops Head
        project.handover_ops_head_signed_by_id = current_user.id
        project.handover_ops_head_signed_at = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=403, detail="Not authorized for handover sign-off.")
    
    # If both have signed off, complete the project
    if project.handover_design_head_signed_by_id and project.handover_ops_head_signed_by_id:
        project.status = "Handed Over"

    db.commit()
    return {"message": "Handover successfully signed."}