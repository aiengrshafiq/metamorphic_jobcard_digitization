# app/api/endpoints/requisition_details.py
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from app.utils import generate_sas_url

from app.api import deps
from app import models

router = APIRouter()

@router.get("/{req_id}", tags=["Requisition Details"])
def get_requisition_details(
    req_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Fetches all details for a single Material Requisition, including related objects.
    """
    requisition = db.query(models.MaterialRequisition).options(
        joinedload(models.MaterialRequisition.project),
        joinedload(models.MaterialRequisition.requested_by),
        joinedload(models.MaterialRequisition.supplier),
        joinedload(models.MaterialRequisition.comments).joinedload(models.MaterialRequisitionComment.comment_by),
        # --- ADD THESE TWO LINES TO FETCH RECEIPT DATA ---
        joinedload(models.MaterialRequisition.receipts).joinedload(models.MaterialReceipt.received_by),
        joinedload(models.MaterialRequisition.receipts).joinedload(models.MaterialReceipt.images),
        # --------------------------------------------------
        joinedload(models.MaterialRequisition.items).joinedload(models.RequisitionItem.material)
    ).filter(models.MaterialRequisition.id == req_id).first()

    if not requisition:
        raise HTTPException(status_code=404, detail="Requisition not found")

    # --- NEW: Generate SAS URLs for all receipt images ---
    for receipt in requisition.receipts:
        for image in receipt.images:
            image.blob_url = generate_sas_url(image.blob_url)
    # ---------------------------------------------------
        
    return requisition

@router.post("/{req_id}/comments", response_class=JSONResponse, tags=["Requisition Details"])
def add_comment(
    req_id: int,
    comment_text: str = Form(...),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Adds a new comment to a Material Requisition.
    """
    new_comment = models.MaterialRequisitionComment(
        requisition_id=req_id,
        comment_by_id=current_user.id,
        comment_text=comment_text
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # Return the new comment with user details
    comment_data = {
        "id": new_comment.id,
        "comment_text": new_comment.comment_text,
        "created_at": new_comment.created_at.isoformat(),
        "comment_by": {
            "name": current_user.name
        }
    }
    return JSONResponse(status_code=201, content=comment_data)