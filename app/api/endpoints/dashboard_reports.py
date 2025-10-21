# app/api/endpoints/dashboard_reports.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from app.api import deps
from app import models
from app import schemas  # <-- 1. IMPORT YOUR NEW SCHEMAS

router = APIRouter()

# --- Job Card Report ---
class JobCardReportData(BaseModel):
    total_count: int
    pending_count: int
    processing_count: int
    done_count: int
    items: List[schemas.JobCardSchema]  # <-- 2. USE THE PYDANTIC SCHEMA

@router.get("/job-cards", tags=["Reports"], response_model=JobCardReportData)
def get_job_card_report(
    db: Session = Depends(deps.get_db),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None
):
    query = db.query(models.JobCard).options(
        joinedload(models.JobCard.project),
        joinedload(models.JobCard.supervisor_user)
    )
    
    if from_date:
        query = query.filter(models.JobCard.date_issued >= from_date)
    if to_date:
        query = query.filter(models.JobCard.date_issued <= to_date)
    if status:
        query = query.filter(models.JobCard.status == status)

    total_count = query.count()
    pending_count = query.filter(models.JobCard.status == 'Pending').count()
    processing_count = query.filter(models.JobCard.status == 'Processing').count()
    done_count = query.filter(models.JobCard.status == 'Done').count()
    items = query.order_by(models.JobCard.date_issued.desc()).all()

    return {
        "total_count": total_count,
        "pending_count": pending_count,
        "processing_count": processing_count,
        "done_count": done_count,
        "items": items
    }

# --- Material Requisition Report ---
class MRReportData(BaseModel):
    total_count: int
    pending_count: int
    approved_count: int
    rejected_count: int
    items: List[schemas.MaterialRequisitionSchema]  # <-- 3. USE THE PYDANTIC SCHEMA

@router.get("/material-requisitions", tags=["Reports"], response_model=MRReportData)
def get_mr_report(
    db: Session = Depends(deps.get_db),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None,
    approval_type: Optional[str] = None,
    approval_status: Optional[str] = None
):
    query = db.query(models.MaterialRequisition).options(
        joinedload(models.MaterialRequisition.project),
        joinedload(models.MaterialRequisition.requested_by)
    )
    
    if from_date:
        query = query.filter(models.MaterialRequisition.request_date >= from_date)
    if to_date:
        query = query.filter(models.MaterialRequisition.request_date <= to_date)
    if status:
        query = query.filter(models.MaterialRequisition.status == status)
    
    if approval_type and approval_status:
        if approval_type == 'mr_approval':
            query = query.filter(models.MaterialRequisition.mr_approval == approval_status)
        elif approval_type == 'pm_approval':
            query = query.filter(models.MaterialRequisition.pm_approval == approval_status)
        elif approval_type == 'qs_approval':
            query = query.filter(models.MaterialRequisition.qs_approval == approval_status)

    total_count = query.count()
    pending_count = query.filter(models.MaterialRequisition.status == 'Pending').count()
    approved_count = query.filter(models.MaterialRequisition.status == 'Approved').count()
    rejected_count = query.filter(models.MaterialRequisition.status == 'Rejected').count()
    items = query.order_by(models.MaterialRequisition.request_date.desc()).all()

    return {
        "total_count": total_count,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "items": items
    }

# --- LPO Report ---
class LPOReportData(BaseModel):
    total_count: int
    pending_count: int
    approved_count: int
    rejected_count: int
    total_value_approved: float
    items: List[schemas.LPOSchema]  # <-- 4. USE THE PYDANTIC SCHEMA

@router.get("/lpos", tags=["Reports"], response_model=LPOReportData)
def get_lpo_report(
    db: Session = Depends(deps.get_db),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None
):
    query = db.query(models.LPO).options(
        joinedload(models.LPO.project),
        joinedload(models.LPO.supplier)
    )
    
    if from_date:
        query = query.filter(models.LPO.lpo_date >= from_date)
    if to_date:
        query = query.filter(models.LPO.lpo_date <= to_date)
    if status:
        query = query.filter(models.LPO.status == status)

    total_count = query.count()
    pending_count = query.filter(models.LPO.status == 'Pending').count()
    approved_count = query.filter(models.LPO.status == 'Approved').count()
    rejected_count = query.filter(models.LPO.status == 'Rejected').count()

    # --- 5. FIX FOR SAWarning (Cartesian Product) ---
    # We apply the filter on the *original* query object, not its subquery
    total_value_approved = query.filter(
        models.LPO.status == 'Approved'
    ).with_entities(
        func.sum(models.LPO.grand_total)
    ).scalar() or 0.0
    # ---------------------------------------------

    items = query.order_by(models.LPO.lpo_date.desc()).all()

    return {
        "total_count": total_count,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "total_value_approved": float(total_value_approved),
        "items": items
    }