# app/api/endpoints/design/design_projects.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.api import deps
from app import models, design_models
from app.design_models import DesignPhaseName, DesignTaskStatus

router = APIRouter()

# --- Deliverable Templates (as defined in the spec) ---
# This is our single source of truth for what tasks are created for each phase.
DELIVERABLE_TEMPLATES = {
    "Phase 2 - Initial Design": [
        "2D Layout", "3D Concept", "Materials/Moodboard", "Reference Page",
        "IDR – Minutes", "Handoff to DC"
    ],
    "Phase 4 - Technical & Authority": [
        "Technical Drawings", "Engineer Sign-off", "Authority Submission"
    ],
    "Phase 5 - Final Package": [
        "Render View List", "Ready for QA", "DM QA Review", "DC Compile & Release"
    ]
}

# --- Pydantic model for receiving data from the frontend ---
class DesignProjectCreate(BaseModel):
    name: str
    client: str
    phases: List[str] # e.g., ["Phase 2 - Initial Design", "Phase 4 - Technical & Authority"]

# --- API Endpoint ---
@router.post("/", tags=["Design"])
def create_design_project(
    project_data: DesignProjectCreate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Creates a new Design Project, its selected Phases, and all the default
    Tasks for each phase based on templates.
    """
    try:
        # 1. Create the main Design Project
        new_project = design_models.DesignProject(
            name=project_data.name,
            client=project_data.client,
            created_by_id=current_user.id
        )
        db.add(new_project)
        db.flush() # Flush to get the new_project.id

        # 2. Loop through the selected phases from the form
        for phase_name_str in project_data.phases:
            # Convert the string name to our Enum member
            phase_name_enum = DesignPhaseName(phase_name_str)
            
            # Create the Design Phase
            new_phase = design_models.DesignPhase(
                project_id=new_project.id,
                name=phase_name_enum
            )
            db.add(new_phase)
            db.flush() # Flush to get the new_phase.id

            # 3. Get the tasks for this phase from our template and create them
            tasks_for_phase = DELIVERABLE_TEMPLATES.get(phase_name_str, [])
            for task_title in tasks_for_phase:
                new_task = design_models.DesignTask(
                    phase_id=new_phase.id,
                    title=task_title,
                    status=DesignTaskStatus.OPEN # Default status
                )
                db.add(new_task)

        db.commit()
        db.refresh(new_project)
        return {"message": "Design project created successfully!", "project_id": new_project.id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")