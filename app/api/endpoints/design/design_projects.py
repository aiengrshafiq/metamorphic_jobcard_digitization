# app/api/endpoints/design/design_projects.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload, selectinload 
from pydantic import BaseModel
from typing import List
from pydantic import conint

from app.api import deps
from app import models, design_models
from app.design_models import DesignPhaseName, DesignTaskStatus


from typing import Optional # Ensure Optional is imported
from datetime import date # Ensure date is imported
from datetime import datetime, timezone

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
    #projects = db.query(design_models.DesignProject).order_by(design_models.DesignProject.id.desc()).all()
    projects = (
        db.query(design_models.DesignProject)
        .filter(design_models.DesignProject.status != "Completed")
        .order_by(design_models.DesignProject.id.desc())
        .all()
    )
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

# Define a Pydantic model for the request body to keep it clean
class TaskAssignmentData(BaseModel):
    owner_id: int
    due_date: Optional[date] = None

@router.post("/tasks/{task_id}/assign", tags=["Design"])
def assign_design_task(
    task_id: int,
    assignment_data: TaskAssignmentData, # Use the Pydantic model
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Assigns a task to a user and sets its due date."""
    # Security Check for Design Manager role
    user_roles = {role.name for role in current_user.roles}
    if "Design Manager" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized for this action")

    task = db.query(design_models.DesignTask).filter(design_models.DesignTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.owner_id = assignment_data.owner_id
    task.due_date = assignment_data.due_date
    db.commit()
    
    return {"message": "Task assigned successfully."}


@router.post("/projects/{project_id}/close", tags=["Design"])
def close_design_project(
    project_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Checks if all phases in a project are complete and then closes the project.
    """
    user_roles = {role.name for role in current_user.roles}
    if "Design Manager" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized for this action.")

    project = db.query(design_models.DesignProject).options(
        selectinload(design_models.DesignProject.phases)
    ).filter(design_models.DesignProject.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    
    if project.status == "Completed":
        raise HTTPException(status_code=400, detail="This project is already completed.")

    for phase in project.phases:
        if phase.status != "Completed":
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot close project: Phase '{phase.name.value}' is not yet completed."
            )
            
    # All gates passed, update the project status and close date
    project.status = "Completed"
    project.closed_at = datetime.now(timezone.utc) # Set the close date
    db.commit()
    
    return {"message": "Project has been successfully closed."}


@router.get("/allprojects/completed", tags=["Design"])
def get_completed_design_projects(db: Session = Depends(deps.get_db)):
    """Fetches a list of all completed Design Projects."""
    projects = db.query(design_models.DesignProject).filter(
        design_models.DesignProject.status == 'Completed'
    ).order_by(design_models.DesignProject.closed_at.desc()).all()
    return projects

