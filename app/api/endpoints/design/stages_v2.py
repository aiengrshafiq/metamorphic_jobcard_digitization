# app/api/endpoints/design/stages_v2.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

from app.api import deps
from app import models
from app.design_v2_models import DesignStage, SiteVisitLog, StageStatus

router = APIRouter()

class SiteVisitUpdate(BaseModel):
    meeting_held_at: datetime
    mom_link: HttpUrl
    site_photos_link: HttpUrl
    updated_brief_link: HttpUrl

@router.post("/{stage_id}/complete-2a", tags=["Design V2 Stages"])
def complete_stage_2a(
    stage_id: int,
    update_data: SiteVisitUpdate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    stage = db.query(DesignStage).filter_by(id=stage_id).first()
    if not stage or stage.status != StageStatus.IN_PROGRESS:
        raise HTTPException(status_code=404, detail="Active Stage 2A not found.")

    # Log the compliance data
    log_entry = db.query(SiteVisitLog).filter_by(stage_id=stage_id).first()
    if not log_entry:
        log_entry = SiteVisitLog(stage_id=stage_id)
        db.add(log_entry)

    log_entry.meeting_held_at = update_data.meeting_held_at
    log_entry.mom_link = str(update_data.mom_link)
    log_entry.site_photos_link = str(update_data.site_photos_link)
    log_entry.updated_brief_link = str(update_data.updated_brief_link)

    # Gate Logic: Unlock the next stage
    next_stage = db.query(DesignStage).filter_by(project_id=stage.project_id, order=stage.order + 1).first()
    if next_stage:
        next_stage.status = StageStatus.IN_PROGRESS

    stage.status = StageStatus.COMPLETED
    db.commit()
    return {"message": "Stage 2A completed successfully. Stage 3 is now unlocked."}


@router.post("/{stage_id}/sign-off", tags=["Design V2 Stages"])
def sign_off_stage_5(
    stage_id: int,
    discipline: str = Body(..., embed=True),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user)
):
    """Logs an interdisciplinary sign-off for a Stage 5 task."""
    stage = db.query(DesignStage).filter_by(id=stage_id).first()
    if not stage or stage.name != StageName.STAGE_5:
        raise HTTPException(status_code=404, detail="Stage 5 not found.")

    new_signoff = design_v2_models.InterdisciplinarySignoff(
        stage_id=stage_id,
        discipline=discipline,
        is_approved=True,
        signed_off_at=datetime.now(timezone.utc),
        signed_off_by_id=current_user.id
    )
    db.add(new_signoff)
    db.commit()
    return {"message": f"{discipline} review has been signed off."}