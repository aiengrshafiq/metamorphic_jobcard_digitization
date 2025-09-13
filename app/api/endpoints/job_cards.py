# app/api/endpoints/job_cards.py
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import date

from app.api import deps
from app import models
from app.utils import generate_job_card_number

router = APIRouter()

@router.post("/", response_class=JSONResponse, tags=["Job Cards"])
async def create_job_card(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    project_id: int = Form(...),
    job_card_no: str = Form(...),
    date_issued: date = Form(...),
    site_location: str = Form(...),
    # site_engineer_id: int = Form(...),
    # supervisor_id: int = Form(...),
    # foreman_id: int = Form(...),
    task_details: List[str] = Form(...),
    quantity: List[Optional[str]] = Form(...),
    units: List[Optional[str]] = Form(...),
    priority: List[Optional[int]] = Form(...),
    start_date: List[Optional[date]] = Form(...),
    end_date: List[Optional[date]] = Form(...),
    assigned_crew: List[Optional[str]] = Form(...),
    site_engineer_user_id: int = Form(...),
    supervisor_user_id: int = Form(...),
    foreman_user_id: int = Form(...)
):
    if db.query(models.JobCard).filter(models.JobCard.job_card_no == job_card_no).first():
        return JSONResponse(status_code=400, content={"message": f"Job Card No '{job_card_no}' already exists."})
    try:
        new_job_card = models.JobCard(
            project_id=project_id,
            job_card_no=job_card_no,
            date_issued=date_issued,
            site_location=site_location,
            created_by_id=current_user.id, # Automatically set the creator
            site_engineer_user_id=site_engineer_user_id,
            supervisor_user_id=supervisor_user_id,
            foreman_user_id=foreman_user_id,
            site_engineer_id=1,
            supervisor_id=1,
            foreman_id=1
        )
        db.add(new_job_card)
        db.flush()

        for i in range(len(task_details)):
            if not task_details[i].strip():
                continue
            new_task = models.Task(
                job_card_id=new_job_card.id,
                task_details=task_details[i],
                quantity=float(quantity[i]) if quantity[i] and quantity[i].strip() else None,
                units=units[i],
                priority=priority[i] if priority[i] else 3,
                start_date=start_date[i],
                end_date=end_date[i],
                assigned_crew=assigned_crew[i]
            )
            db.add(new_task)
        db.commit()
        return JSONResponse(
            status_code=200,
            content={
                "message": "Job Card created successfully!",
                "next_job_card_no": generate_job_card_number(db, site_location)
            }
        )
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An error occurred: {e}"})

@router.post("/api/tasks/{task_id}/update-status", response_class=JSONResponse, tags=["Tasks API"])
async def update_task_status(
    task_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    status: str = Form(...)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).options(joinedload(models.Task.job_card)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = status
    db.commit()

    job_card = task.job_card
    pending_or_processing_tasks_count = db.query(models.Task).filter(
        models.Task.job_card_id == job_card.id,
        models.Task.status != 'Done'
    ).count()

    job_card_status_changed = False
    if pending_or_processing_tasks_count == 0:
        if job_card.status != 'Done':
            job_card.status = 'Done'
            job_card_status_changed = True
    else:
        if job_card.status == 'Done':
            job_card.status = 'Pending'
            job_card_status_changed = True

    if job_card_status_changed:
        db.commit()
        db.refresh(job_card)

    return {
        "message": f"Task {task_id} status updated to {status}",
        "job_card_id": job_card.id,
        "job_card_status": job_card.status if job_card_status_changed else None
    }

@router.get("/api/generate-job-card-no", tags=["Job Cards API"])
async def get_new_job_card_no(site_location: str, db: Session = Depends(deps.get_db)):
    if not site_location:
        raise HTTPException(status_code=400, detail="Site location is required.")
    return {"job_card_no": generate_job_card_number(db, site_location)}

@router.get("/api/job-cards/{job_card_id}/tasks", response_class=JSONResponse, tags=["Job Cards API"])
async def get_job_card_tasks(job_card_id: int, db: Session = Depends(deps.get_db)):
    tasks = db.query(models.Task).filter(models.Task.job_card_id == job_card_id).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found for this Job Card.")
    return [{"id": task.id, "task_details": task.task_details} for task in tasks]