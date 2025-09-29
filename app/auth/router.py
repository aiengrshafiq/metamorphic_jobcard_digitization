# app/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
import uuid
from user_agents import parse

from app import models, schemas
from app.api import deps
from app.auth import security
from app.core.config import settings

router = APIRouter()

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    request: Request,
    db: Session = Depends(deps.get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Standard OAuth2 password flow. Takes a username (email) and password.
    Returns an access token.
    """
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    # --- ADD THIS LOGGING LOGIC ---
    # --- PARSE THE USER AGENT ---
    user_agent_string = request.headers.get('user-agent', '')
    user_agent = parse(user_agent_string)
    
    # Determine device type
    if user_agent.is_mobile:
        device_type = "Mobile"
    elif user_agent.is_tablet:
        device_type = "Tablet"
    elif user_agent.is_pc:
        device_type = "PC/Laptop"
    else:
        device_type = "Other"
    # -----------------------------
    log_entry = models.AuthLog(
        ip_address=request.client.host,
        user_agent=request.headers.get('user-agent'),
        # --- SAVE THE PARSED DATA ---
        browser=f"{user_agent.browser.family} {user_agent.browser.version_string}",
        os=f"{user_agent.os.family} {user_agent.os.version_string}",
        device=f"{device_type} ({user_agent.device.family})"
        # -----------------------------
    )

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        log_entry.event_type = f"Login Failure: {form_data.username}"
        db.add(log_entry)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    log_entry.user_id = user.id
    log_entry.event_type = "Login Success"
    db.add(log_entry)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # access_token = security.create_access_token(
    #     data={"sub": user.email}, expires_delta=access_token_expires
    # )
    # db.commit()
    # return {"access_token": access_token, "token_type": "bearer"}

    if user:
        user.session_id = uuid.uuid4() # Generate a new session ID, invalidating old ones
        # ... add the log entry ...
        access_token = security.create_access_token(
            data={"sub": user.email, "jti": str(user.session_id)}, # Add session ID to token
            expires_delta=access_token_expires
        )
        db.commit()
        return {"access_token": access_token, "token_type": "bearer"}