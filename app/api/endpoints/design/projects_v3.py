# app/api/endpoints/design/projects_v3.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload, joinedload
from app.api import deps
from app.design_v3_models import DesignProjectV3, DesignStageV3, DesignTaskV3,MeasurementRequisition

router = APIRouter()

@router.get("/{project_id}", tags=["Design V3 Projects"])
def get_design_project_v3_details(project_id: int, db: Session = Depends(deps.get_db)):
    """Fetches a single V3 Design Project with all its stages, tasks, and compliance data."""
    project = db.query(DesignProjectV3).options(
        selectinload(DesignProjectV3.stages).options(
            selectinload(DesignStageV3.tasks).joinedload(DesignTaskV3.owner),
            selectinload(DesignStageV3.site_visit_log),
            selectinload(DesignStageV3.measurement_requisition).joinedload(MeasurementRequisition.vendor)
        )
    ).filter(DesignProjectV3.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Design project not found")
    
    return project