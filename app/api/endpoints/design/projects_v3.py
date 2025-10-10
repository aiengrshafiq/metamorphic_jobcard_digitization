# app/api/endpoints/design/projects_v3.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload, joinedload
from app.api import deps
from app.design_v3_models import DesignProjectV3, DesignStageV3, DesignTaskV3,MeasurementRequisition,InterdisciplinarySignoff

router = APIRouter()

@router.get("/{project_id}", tags=["Design V3 Projects"])
def get_design_project_v3_details(project_id: int, db: Session = Depends(deps.get_db)):
    """Fetches a single V3 Design Project with all its stages, tasks, and compliance data."""
    # project = db.query(DesignProjectV3).options(
    #     selectinload(DesignProjectV3.stages).options(
    #         selectinload(DesignStageV3.tasks).joinedload(DesignTaskV3.owner),
    #         selectinload(DesignStageV3.site_visit_log),
    #         selectinload(DesignStageV3.measurement_requisition).joinedload(MeasurementRequisition.vendor),
    #         selectinload(DesignStageV3.interdisciplinary_signoffs).joinedload(InterdisciplinarySignoff.signed_off_by),
    #         joinedload(DesignProjectV3.handover_design_head_signed_by),
    #         joinedload(DesignProjectV3.handover_ops_head_signed_by)
    #     )
    # ).filter(DesignProjectV3.id == project_id).first()
    project = db.query(DesignProjectV3).options(
        # --- THIS IS THE FIX ---
        # Load the stages, and within each stage, load its related data
        selectinload(DesignProjectV3.stages).options(
            selectinload(DesignStageV3.tasks).joinedload(DesignTaskV3.owner),
            selectinload(DesignStageV3.site_visit_log),
            selectinload(DesignStageV3.measurement_requisition).joinedload(MeasurementRequisition.vendor),
            #selectinload(DesignStageV3.qs_validation).joinedload(QSValidation.validated_by),
            selectinload(DesignStageV3.interdisciplinary_signoffs).joinedload(InterdisciplinarySignoff.signed_off_by)
        ),
        # Load the project-level handover relationships separately at the top level
        joinedload(DesignProjectV3.handover_design_head_signed_by),
        joinedload(DesignProjectV3.handover_ops_head_signed_by)
        # -----------------------
    ).filter(DesignProjectV3.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Design project not found")
    
    return project