# app/api/endpoints/design/design_projects.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload, selectinload 
from pydantic import BaseModel
from typing import List
from pydantic import conint

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

@router.get("/", tags=["Design"])
def get_design_projects(db: Session = Depends(deps.get_db)):
    """Fetches a list of all Design Projects."""
    projects = db.query(design_models.DesignProject).order_by(design_models.DesignProject.id.desc()).all()
    return projects

@router.get("/{project_id}", tags=["Design"])
def get_design_project_details(project_id: int, db: Session = Depends(deps.get_db)):
    """Fetches a single Design Project with all its phases and tasks."""
    project = db.query(design_models.DesignProject).options(
        selectinload(design_models.DesignProject.phases).selectinload(design_models.DesignPhase.tasks).joinedload(design_models.DesignTask.owner)
    ).filter(design_models.DesignProject.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Design project not found")
    
    return project

@router.post("/tasks/{task_id}/assign", tags=["Design"])
def assign_design_task(
    task_id: int,
    owner_id: conint(gt=0) = Body(..., embed=True), # conint(gt=0) ensures a valid ID is sent
    db: Session = Depends(deps.get_db)
):
    """Assigns a task to a user (owner)."""
    task = db.query(design_models.DesignTask).filter(design_models.DesignTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.owner_id = owner_id
    db.commit()
    
    return {"message": "Task assigned successfully."}