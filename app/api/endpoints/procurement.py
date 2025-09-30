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
from typing import List
from sqlalchemy import or_

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

    # --- V3 DATA FILTERING LOGIC ---
    # Start with a base query
    query = db.query(models.MaterialRequisition).filter(
        models.MaterialRequisition.status == 'Pending'
    ).options(
        joinedload(models.MaterialRequisition.project),
        joinedload(models.MaterialRequisition.requested_by)
    )

    # Define roles that can see ALL requisitions
    privileged_roles = {
        'Super Admin', 'Admin', 'Operation Mananger', 
        'Project Manager', 'Procurement', 'QS'
    }
    is_privileged = bool(privileged_roles.intersection(context["user_roles"]))

    # If the user is NOT privileged, apply a filter
    if not is_privileged:
        # This will apply to roles like 'Supervisor/Site Officer'
        current_user_id = context["user"].id
        query = query.filter(models.MaterialRequisition.requested_by_id == current_user_id)
    
    # Execute the final query
    requisitions = query.order_by(models.MaterialRequisition.request_date.desc()).all()
    # ------------------------------------
    
    context.update({
        "page_title": "Procurement Dashboard",
        "requisitions": requisitions
    })
    return templates.TemplateResponse("procurement_list.html", context)


@router.get("/material-requisitions-delivered", response_class=HTMLResponse, tags=["Procurement"])
async def list_material_requisitions_delivered(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db),
    search: Optional[str] = None
):
    if isinstance(context, RedirectResponse):
        return context

    # --- V3 DATA FILTERING LOGIC ---
    # Start with a base query
    query = db.query(models.MaterialRequisition).filter(
        # models.MaterialRequisition.status == 'Delivered'
         models.MaterialRequisition.mr_approval == 'Approved'
    ).options(
        joinedload(models.MaterialRequisition.project),
        joinedload(models.MaterialRequisition.requested_by)
    )

     # --- 2. ADD THIS SEARCH LOGIC ---
    if search:
        search_term = f"%{search}%"
        query = query.join(models.Project).filter(
            or_(
                models.MaterialRequisition.mr_number.ilike(search_term),
                models.Project.name.ilike(search_term)
            )
        )
    # --------------------------------

    # Define roles that can see ALL requisitions
    privileged_roles = {
        'Super Admin', 'Admin', 'Operation Mananger', 
        'Project Manager', 'Procurement', 'QS'
    }
    is_privileged = bool(privileged_roles.intersection(context["user_roles"]))

    # If the user is NOT privileged, apply a filter
    if not is_privileged:
        # This will apply to roles like 'Supervisor/Site Officer'
        current_user_id = context["user"].id
        query = query.filter(models.MaterialRequisition.requested_by_id == current_user_id)

    
    
    # Execute the final query
    requisitions = query.order_by(models.MaterialRequisition.request_date.desc()).all()
    # ------------------------------------
    
    context.update({
        "page_title": "Procurement Dashboard",
        "requisitions": requisitions
    })
    return templates.TemplateResponse("procurement_list_delivered.html", context)


# @router.get("/material-requisition/{req_id}", response_class=HTMLResponse, tags=["Procurement"])
# async def process_material_requisition_form(
#     req_id: int,
#     context: dict = Depends(deps.get_template_context),
#     db: Session = Depends(deps.get_db)
# ):
#     if isinstance(context, RedirectResponse):
#         return context

#     req = db.query(models.MaterialRequisition).options(
#         joinedload(models.MaterialRequisition.project),
#         joinedload(models.MaterialRequisition.requested_by),
#         joinedload(models.MaterialRequisition.items).joinedload(models.RequisitionItem.material)
#     ).filter(models.MaterialRequisition.id == req_id).first()

#     if not req:
#         raise HTTPException(status_code=404, detail="Requisition not found")

#     context.update({
#         "page_title": f"Process Requisition #{req.id}",
#         "req": req,
#         "suppliers": db.query(models.Supplier).order_by(models.Supplier.name).all(),
#         "approval_statuses": app_config.get('approval_statuses', []),
#         "requisition_statuses": app_config.get('requisition_statuses', []),
#     })
#     return templates.TemplateResponse("procurement_update.html", context)


@router.get("/material-requisition/{req_id}/process", response_class=HTMLResponse, tags=["Procurement"])
async def process_or_finalize_requisition_form(
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

    # Determine which page to show based on the MR status
    if req.status == "Draft":
        template_name = "procurement_finalize.html"
        context["page_title"] = f"Finalize Draft MR #{req.id}"
        # Fetch materials needed for the finalize form
        context["materials"] = db.query(models.Material).order_by(models.Material.name).all()
    else:
        template_name = "procurement_update.html"
        context["page_title"] = f"Process Requisition #{req.id}"
        context["suppliers"] = db.query(models.Supplier).order_by(models.Supplier.name).all()
        context["approval_statuses"] = app_config.get('approval_statuses', [])
        context["requisition_statuses"] = app_config.get('requisition_statuses', [])

    context["req"] = req
    return templates.TemplateResponse(template_name, context)


# --- API POST Routes (Unchanged - Already Correct) ---

@router.post("/material-requisitions/", response_class=JSONResponse, tags=["Procurement"])
async def create_material_requisition(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    request_date: date = Form(...),
    project_id: int = Form(...),
    requested_by_id: int = Form(...),
    material_type: str = Form(...),
    urgency: str = Form(...),
    required_delivery_date: date = Form(...),
    job_card_ids: List[int] = Form(None),
    material_ids: List[str] = Form(...),
    quantities: List[str] = Form(...),
    special_notes: Optional[str] = Form(None),
    submit_action: str = Form(...) 
):
    try:
         # --- NEW: MR Number Generation Logic ---
        # Find the highest existing MR number
        last_mr = db.query(func.max(models.MaterialRequisition.mr_number)).scalar()
        
        # If none exist, start from 57. Otherwise, increment the last one.
        next_mr_num = 57 if not last_mr else int(last_mr.split('-')[1]) + 1
        
        # Format the new MR number
        new_mr_number = f"MR-{next_mr_num:06d}"

        # --- NEW: Auto-approval logic for PM ---
        user_roles = {role.name for role in current_user.roles}
        pm_status = "Pending" # Default status
        if "Project Manager" in user_roles:
            pm_status = "Approved"
        # ------------------------------------
        # --- NEW: Logic to handle Draft vs. Final Submission ---
        is_draft = submit_action == "save_draft"

        # Line items are only required if it's NOT a draft
        if not is_draft and not material_ids:
            raise HTTPException(status_code=400, detail="At least one material item is required for final submission.")
        if not is_draft and len(material_ids) != len(quantities):
            raise HTTPException(status_code=400, detail="Mismatch between materials and quantities.")
        # ----------------------------------------------------

        requisition = models.MaterialRequisition(
            mr_number=new_mr_number,
            request_date=request_date,
            project_id=project_id,
            requested_by_id=requested_by_id,
            material_type=material_type,
            #material_with_quantity=material_with_quantity,
            urgency=urgency,
            required_delivery_date=required_delivery_date,
            pm_approval=pm_status,
            special_notes=special_notes,
            created_by_id=current_user.id,
            status="Draft" if is_draft else "Pending",
        )

        if not is_draft:
            # If it's a final submission, items are required.
            if not material_ids or not material_ids[0]:
                raise HTTPException(status_code=400, detail="At least one material item is required for final submission.")
            
            try:
                # Convert string lists to number lists
                final_material_ids = [int(mid) for mid in material_ids if mid]
                final_quantities = [float(qty) for qty in quantities if qty]
                if len(final_material_ids) != len(final_quantities):
                    raise HTTPException(status_code=400, detail="Mismatch between materials and quantities.")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid number format for materials or quantities.")
               
         # --- NEW: Link the selected Job Cards ---
        if job_card_ids:
            job_cards_to_link = db.query(models.JobCard).filter(models.JobCard.id.in_(job_card_ids)).all()
            requisition.job_cards.extend(job_cards_to_link)
        # ------------------------------------
        # --- NEW: Create RequisitionItem objects from the form data ---
        if len(material_ids) != len(quantities):
            raise HTTPException(status_code=400, detail="Mismatch between materials and quantities.")

        if material_ids and quantities:
            for mat_id, qty in zip(material_ids, quantities):
                if not mat_id or not qty:
                    continue
                item = models.RequisitionItem(
                    material_id=mat_id,
                    quantity=qty
                )
                requisition.items.append(item)
        # -----------------------------------------------------------
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


@router.post("/{req_id}/finalize", response_class=JSONResponse, tags=["Procurement"])
async def finalize_material_requisition(
    req_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    material_ids: List[int] = Form(...),
    quantities: List[float] = Form(...)
):
    # Security check can be added here to ensure only Admins can do this

    req = db.query(models.MaterialRequisition).filter(models.MaterialRequisition.id == req_id).first()
    if not req or req.status != "Draft":
        raise HTTPException(status_code=404, detail="Draft requisition not found.")

    # Clear existing items to prevent duplicates
    req.items.clear()

    # Add the new, finalized items
    for mat_id, qty in zip(material_ids, quantities):
        if mat_id and qty:
            item = models.RequisitionItem(material_id=mat_id, quantity=qty)
            req.items.append(item)

    req.status = "Pending" # Change status to enter the approval flow
    db.commit()
    return JSONResponse(status_code=200, content={"message": "Requisition has been finalized and submitted for approval."})


@router.get("/material-requisitions-drafts", response_class=HTMLResponse, tags=["Procurement"])
async def list_draft_requisitions(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context

    # Query for requisitions with the "Draft" status
    draft_requisitions = db.query(models.MaterialRequisition).filter(
        models.MaterialRequisition.status == 'Draft'
    ).options(
        joinedload(models.MaterialRequisition.project),
        joinedload(models.MaterialRequisition.requested_by)
    ).order_by(models.MaterialRequisition.request_date.desc()).all()

    context.update({
        "page_title": "Draft Material Requisitions",
        "requisitions": draft_requisitions
    })
    return templates.TemplateResponse("procurement_list_drafts.html", context)