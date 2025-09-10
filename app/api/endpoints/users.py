# app/api/endpoints/users.py
from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app import models
from app.auth.security import get_password_hash

router = APIRouter()

@router.post("/register", response_class=JSONResponse, tags=["Users"])
async def register_new_user(
    db: Session = Depends(deps.get_db),
    email: str = Form(...),
    password: str = Form(...),
    roles: List[str] = Form(...) # The form will submit a list of role names
):
    """
    Handle new user registration.
    """
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    # Get Role objects from the database based on the submitted role names
    db_roles = db.query(models.Role).filter(models.Role.name.in_(roles)).all()
    if not db_roles:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid roles provided.",
        )

    # Create the new user
    hashed_password = get_password_hash(password)
    new_user = models.User(
        email=email,
        hashed_password=hashed_password,
        is_active=True, # You might want to default this to False and have an email verification step
        roles=db_roles
    )

    db.add(new_user)
    db.commit()

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": f"User '{email}' created successfully! You can now log in."}
    )