# app/api/endpoints/materials.py
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.api import deps
from app import models

router = APIRouter()

@router.post("/last-order-info", tags=["Materials"])
def get_last_order_info(
    material_ids: List[int] = Body(..., embed=True),
    current_req_id: int = Body(..., embed=True),
    db: Session = Depends(deps.get_db)
):
    """
    For a given list of material IDs, finds the most recent
    reposition item for each one, excluding the current requisition.
    """
    history = {}
    for mat_id in material_ids:
        last_item = db.query(models.RequisitionItem).join(
            models.MaterialRequisition
        ).options(
            joinedload(models.RequisitionItem.requisition).joinedload(models.MaterialRequisition.project)
        ).filter(
            models.RequisitionItem.material_id == mat_id,
            models.RequisitionItem.requisition_id != current_req_id # Exclude the current MR
        ).order_by(
            models.MaterialRequisition.request_date.desc()
        ).first()

        if last_item:
            history[mat_id] = {
                "quantity": last_item.quantity,
                "unit": last_item.material.unit,
                "project_name": last_item.requisition.project.name,
                "request_date": last_item.requisition.request_date.isoformat()
            }
    return history