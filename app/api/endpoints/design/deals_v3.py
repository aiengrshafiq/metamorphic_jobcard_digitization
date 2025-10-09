# app/api/endpoints/design/deals_v3.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import Optional, List
from datetime import date

from app.api import deps
from app import models
from app.design_v3_models import Deal, CommitmentPackage
from app.core.config import settings
from azure.storage.blob.aio import BlobServiceClient
from sqlalchemy import func

from app.design_v3_models import Deal, DesignProjectV3, DesignStageV3, StageV3Name, StageV3Status, CommitmentPackage,DesignTaskV3





router = APIRouter()


# --- Reusable logic for creating stages and tasks ---
def _create_stages_and_tasks(db: Session, project: DesignProjectV3):
    # This template defines which tasks are auto-created for each stage
    DELIVERABLE_TEMPLATES_V3 = {
        StageV3Name.INITIAL_DESIGN: ["2D Layout", "SketchUp Model", "Render Set v1", "Preliminary BOQ"],
        # Add other stages with default tasks here in the future
    }
    
    # Create all stages in order
    for i, stage_enum in enumerate(StageV3Name):
        # The first actionable stage is 2A (SITE_VISIT)
        stage_status = StageV3Status.IN_PROGRESS if stage_enum == StageV3Name.SITE_VISIT else StageV3Status.LOCKED
        
        new_stage = DesignStageV3(
            project_id=project.id,
            name=stage_enum,
            status=stage_status,
            order=i + 1
        )
        db.add(new_stage)
        db.flush()
        
        # Create the default tasks for this stage
        tasks_for_stage = DELIVERABLE_TEMPLATES_V3.get(stage_enum, [])
        for task_title in tasks_for_stage:
            new_task = DesignTaskV3(stage_id=new_stage.id, title=task_title)
            db.add(new_task)



@router.post("/", tags=["Design V3 Deals"])
async def create_deal_v3(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    # Form Fields
    project_name: str = Form(...),
    client_name: str = Form(...),
    client_contact: str = Form(...),
    location: str = Form(...),
    contract_type: CommitmentPackage = Form(...),
    budget: float = Form(...),
    payment_date: date = Form(...),
    contract_date: date = Form(...),
    # File Uploads
    initial_brief: UploadFile = File(...),
    floor_plan: UploadFile = File(...),
    as_built: Optional[UploadFile] = File(None)
):
    """Creates a new V3 Deal, uploading attachments to Azure."""
    
    async def upload_to_azure(file: UploadFile) -> str:
        if not file or not file.filename:
            return ""
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        container_name = "deal-attachments"
        async with blob_service_client:
            container_client = blob_service_client.get_container_client(container_name)
            if not await container_client.exists():
                await container_client.create_container()
            
            blob_name = f"{uuid.uuid4()}-{file.filename}"
            blob_client = container_client.get_blob_client(blob_name)
            
            file_contents = await file.read()
            await blob_client.upload_blob(file_contents, overwrite=True)
            return blob_client.url

    # Upload files and get their URLs
    brief_url = await upload_to_azure(initial_brief)
    floor_plan_url = await upload_to_azure(floor_plan)
    as_built_url = await upload_to_azure(as_built) if as_built else None

    new_deal = Deal(
        project_name=project_name, client_name=client_name, client_contact=client_contact,
        location=location, contract_type=contract_type, budget=budget,
        payment_date=payment_date, contract_date=contract_date,
        initial_brief_link=brief_url, floor_plan_link=floor_plan_url, as_built_link=as_built_url,
        sip_id=current_user.id
    )
    
    db.add(new_deal)
    db.commit()
    
    return {"message": "Deal created successfully!", "deal_id": new_deal.id}


@router.get("/", tags=["Design V3 Deals"])
def get_deals_v3(db: Session = Depends(deps.get_db)):
    """Fetches V3 Deals, including the ID of any project already created from them."""
    deals_with_projects = db.query(Deal, DesignProjectV3.id.label("project_id")) \
        .outerjoin(DesignProjectV3, Deal.id == DesignProjectV3.deal_id) \
        .options(joinedload(Deal.sip)).order_by(Deal.id.desc()).all()
    
    results = []
    for deal, project_id in deals_with_projects:
        deal_dict = {c.name: getattr(deal, c.name) for c in deal.__table__.columns}
        deal_dict['project_id'] = project_id
        deal_dict['sip'] = {"name": deal.sip.name} if deal.sip else {"name": "N/A"}
        results.append(deal_dict)
    return results


@router.post("/{deal_id}/activate", tags=["Design V3 Deals"])
def activate_deal_v3(
    deal_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Creates a new V3 Design Project from a Deal."""
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found.")
        
    if deal.project:
        raise HTTPException(status_code=400, detail="A project has already been activated for this deal.")

    new_project = DesignProjectV3(
        name=deal.project_name,
        client=deal.client_name,
        created_by_id=current_user.id,
        deal_id=deal.id
    )
    db.add(new_project)
    db.flush()
    
    _create_stages_and_tasks(db, new_project)
    
    db.commit()
    return {"message": "Project activated successfully!", "project_id": new_project.id}