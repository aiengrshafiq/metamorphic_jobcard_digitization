# app/api/endpoints/procurement.py
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from datetime import date
import yaml
from pathlib import Path
import os

from app.api import deps
from app import models

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- Safe Configuration Loading (making this file self-sufficient) ---
def _load_config() -> dict:
    path = Path(os.getenv("APP_CONFIG_PATH", "config.yaml"))
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Warning: Config file at {path} not found.")
        return {}
app_config = _load_config()
# --- End Config Loading ---


# --- Page-Rendering GET Routes (Refactored) ---

@router.get("/material-requisitions", response_class=HTMLResponse, tags=["Procurement"])
async def list_material_requisitions(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context

    requisitions = db.query(models.MaterialRequisition).filter(
        models.MaterialRequisition.status == 'Pending'
    ).options(
        joinedload(models.MaterialRequisition.project),
        joinedload(models.MaterialRequisition.requested_by)
    ).order_by(models.MaterialRequisition.request_date).all()
    
    context.update({
        "page_title": "Procurement Dashboard",
        "requisitions": requisitions
    })
    return templates.TemplateResponse("procurement_list.html", context)


@router.get("/material-requisition/{req_id}", response_class=HTMLResponse, tags=["Procurement"])
async def process_material_requisition_form(
    req_id: int,
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context

    req = db.query(models.MaterialRequisition).options(
        joinedload(models.MaterialRequisition.project),
        joinedload(models.MaterialRequisition.requested_by)
    ).filter(models.MaterialRequisition.id == req_id).first()

    if not req:
        raise HTTPException(status_code=404, detail="Requisition not found")

    context.update({
        "page_title": f"Process Requisition #{req.id}",
        "req": req,
        "suppliers": db.query(models.Supplier).order_by(models.Supplier.name).all(),
        "approval_statuses": app_config.get('approval_statuses', []),
        "requisition_statuses": app_config.get('requisition_statuses', []),
    })
    return templates.TemplateResponse("procurement_update.html", context)


# --- API POST Routes (Unchanged - Already Correct) ---

@router.post("/material-requisitions/", response_class=JSONResponse, tags=["Procurement"])
async def create_material_requisition(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    request_date: date = Form(...),
    project_id: int = Form(...),
    requested_by_id: int = Form(...),
    material_type: str = Form(...),
    material_with_quantity: str = Form(...),
    urgency: str = Form(...),
    required_delivery_date: date = Form(...)
):
    try:
         # --- NEW: MR Number Generation Logic ---
        # Find the highest existing MR number
        last_mr = db.query(func.max(models.MaterialRequisition.mr_number)).scalar()
        
        # If none exist, start from 57. Otherwise, increment the last one.
        next_mr_num = 57 if not last_mr else int(last_mr.split('-')[1]) + 1
        
        # Format the new MR number
        new_mr_number = f"MR-{next_mr_num:06d}"
        # ------------------------------------
        requisition = models.MaterialRequisition(
            mr_number=new_mr_number,
            request_date=request_date,
            project_id=project_id,
            requested_by_id=requested_by_id,
            material_type=material_type,
            material_with_quantity=material_with_quantity,
            urgency=urgency,
            required_delivery_date=required_delivery_date
        )
        db.add(requisition)
        db.commit()
        return JSONResponse(status_code=200, content={"message": "Material requisition submitted successfully!"})
    except Exception as e:
        db.rollback()
        # Provide a more specific error for unique constraint violation
        if "unique constraint" in str(e).lower():
            return JSONResponse(status_code=400, content={"message": "A database error occurred. It's possible the MR Number already exists."})
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})


@router.post("/api/material-requisitions/{req_id}", response_class=JSONResponse, tags=["Procurement API"])
async def update_material_requisition(
    req_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    supplier_id: int = Form(...),
    status: str = Form(...),
    lpo_number: Optional[str] = Form(None),
    pm_approval: Optional[str] = Form(None),
    qs_approval: Optional[str] = Form(None),
    payment_status: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None)
):
    req = db.query(models.MaterialRequisition).filter(models.MaterialRequisition.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requisition not found")
    try:
        

        req.supplier_id = supplier_id
        req.lpo_number = lpo_number
        req.pm_approval = pm_approval
        req.qs_approval = qs_approval
        req.payment_status = payment_status
        req.remarks = remarks
        req.status = status
        db.commit()
        return JSONResponse(status_code=200, content={"message": f"Requisition {req.mr_number} updated successfully!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})