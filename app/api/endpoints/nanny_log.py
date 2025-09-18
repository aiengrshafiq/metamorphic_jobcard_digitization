# app/api/endpoints/nanny_log.py
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.api import deps
from app import models, schemas

router = APIRouter()

@router.post("/", response_class=JSONResponse, tags=["Nanny Log"])
async def create_nanny_log(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
    # General
    log_date: date = Form(...),
    nanny_id: int = Form(...),
    # Hygiene
    handwashing_checks: List[str] = Form(None),
    environment_checks: List[str] = Form(None),
    # Meals
    breakfast_details: Optional[str] = Form(None),
    breakfast_amount: Optional[str] = Form(None),
    lunch_details: Optional[str] = Form(None),
    lunch_amount: Optional[str] = Form(None),
    snack_details: Optional[str] = Form(None),
    snack_amount: Optional[str] = Form(None),
    dinner_details: Optional[str] = Form(None),
    dinner_amount: Optional[str] = Form(None),
    # Hydration
    hydration_morning_cups: Optional[str] = Form(None),
    hydration_afternoon_cups: Optional[str] = Form(None),
    hydration_evening_cups: Optional[str] = Form(None),
    restricted_foods_given: bool = Form(False),
    restricted_foods_details: Optional[str] = Form(None),
    # Routine
    nap_duration_minutes: Optional[int] = Form(None),
    bedtime_by_830pm: bool = Form(False),
    total_sleep_hours: Optional[str] = Form(None),
    # Activities
    outdoor_play_completed: bool = Form(False),
    outdoor_play_minutes: Optional[int] = Form(None),
    screen_time_minutes: Optional[int] = Form(None),
    # Health
    temperature_celsius: Optional[float] = Form(None),
    appetite: Optional[str] = Form(None),
    behavior: Optional[str] = Form(None),
    signs_of_illness: Optional[str] = Form(None),
    nanny_notes: Optional[str] = Form(None),
):
    try:
        new_log = models.NannyLog(
            created_by_id=current_user.id,
            log_date=log_date,
            nanny_id=nanny_id,
            handwashing_checks=",".join(handwashing_checks) if handwashing_checks else None,
            environment_checks=",".join(environment_checks) if environment_checks else None,
            breakfast_details=breakfast_details, breakfast_amount=breakfast_amount,
            lunch_details=lunch_details, lunch_amount=lunch_amount,
            snack_details=snack_details, snack_amount=snack_amount,
            dinner_details=dinner_details, dinner_amount=dinner_amount,
            hydration_morning_cups=hydration_morning_cups,
            hydration_afternoon_cups=hydration_afternoon_cups,
            hydration_evening_cups=hydration_evening_cups,
            restricted_foods_given=restricted_foods_given,
            restricted_foods_details=restricted_foods_details,
            nap_duration_minutes=nap_duration_minutes,
            bedtime_by_830pm=bedtime_by_830pm,
            total_sleep_hours=total_sleep_hours,
            outdoor_play_completed=outdoor_play_completed,
            outdoor_play_minutes=outdoor_play_minutes,
            screen_time_minutes=screen_time_minutes,
            temperature_celsius=temperature_celsius,
            appetite=appetite,
            behavior=behavior,
            signs_of_illness=signs_of_illness,
            nanny_notes=nanny_notes
        )
        db.add(new_log)
        db.commit()
        return JSONResponse(status_code=200, content={"message": "Nanny log submitted successfully!"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"message": f"An unexpected error occurred: {e}"})