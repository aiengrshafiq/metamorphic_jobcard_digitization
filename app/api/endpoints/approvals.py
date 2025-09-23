# app/api/endpoints/approvals.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field
from typing import Literal

from app.api import deps
from app import models

router = APIRouter()

class ApprovalUpdate(BaseModel):
    approval_type: Literal['pm', 'qs', 'mr']
    new_status: Literal['Approved', 'Rejected']

@router.get("/pending", tags=["Approvals"])
def get_pending_approvals(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Fetches material requisitions pending approval for the current user.
    This endpoint is role-aware and handles sequential logic.
    """
    user_roles = {role.name for role in current_user.roles}
    query = db.query(models.MaterialRequisition).options(
        joinedload(models.MaterialRequisition.project),
        joinedload(models.MaterialRequisition.requested_by)
    ).order_by(models.MaterialRequisition.request_date.desc())

    pending_items = []
    
    # For Project Managers: Show items awaiting PM approval THAT ARE MR-APPROVED.
    if models.UserRole.PROJECT_MANAGER in user_roles:
        pm_pending = query.filter(
            models.MaterialRequisition.pm_approval == 'Pending',
            models.MaterialRequisition.mr_approval == 'Approved'  # <-- ADD THIS CONDITION
        ).all()
        for item in pm_pending:
            item.pending_for = 'PM'
            item.is_actionable = True
            pending_items.append(item)

    # For QS: Show items awaiting QS approval THAT ARE MR-APPROVED.
    if models.UserRole.QS in user_roles:
        qs_pending = query.filter(
            models.MaterialRequisition.qs_approval == 'Pending',
            models.MaterialRequisition.mr_approval == 'Approved'  # <-- ADD THIS CONDITION
        ).all()
        for item in qs_pending:
            if item not in pending_items:
                item.pending_for = 'QS'
                # The logic that an item is only actionable for a QS if the PM 
                # has also approved it remains correct.
                item.is_actionable = (item.pm_approval == 'Approved')
                pending_items.append(item)

    return pending_items


@router.post("/{req_id}/status", response_class=JSONResponse, tags=["Approvals"])
def update_approval_status(
    req_id: int,
    update_data: ApprovalUpdate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Updates the approval status for a specific requisition.
    """
    req = db.query(models.MaterialRequisition).filter(models.MaterialRequisition.id == req_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requisition not found")

    user_roles = {role.name for role in current_user.roles}

    if update_data.approval_type == 'pm':
        if "Project Manager" not in user_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for PM approval")
        req.pm_approval = update_data.new_status
    elif update_data.approval_type == 'qs':
        if "QS" not in user_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for QS approval")
        req.qs_approval = update_data.new_status
    
    elif update_data.approval_type == 'mr':
        if "Procurement" not in user_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for MR approval")
        req.mr_approval = update_data.new_status
    # --------------------------
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid approval type")
        
    db.commit()
    return {"message": f"Requisition {req.id} has been {update_data.new_status.lower()}."}