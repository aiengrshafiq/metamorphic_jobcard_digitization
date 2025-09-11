# app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import Generator

from app.core.database import SessionLocal
from app.core.config import settings
from app import models, schemas
from app.auth.security import ALGORITHM

from fastapi.responses import RedirectResponse
from starlette.requests import Request
from fastapi.templating import Jinja2Templates

# This tells FastAPI where to go to get a token.
# We will create the "/token" endpoint in the next step.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def get_db() -> Generator:
    """Dependency to get a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> models.User:
    """Dependency to get the current user from a JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.email == token_data.email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)) -> models.User:
    """
    Dependency to get a user from the access_token cookie.
    Redirects to the login page if the cookie is not valid.
    """
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return RedirectResponse(url="/login")
    except JWTError:
        return RedirectResponse(url="/login")
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not user.is_active:
        return RedirectResponse(url="/login")
        
    return user

def get_template_context(
    request: Request, 
    current_user: models.User = Depends(get_current_user_from_cookie)
) -> dict | RedirectResponse:
    """
    A dependency that prepares the common context dictionary for templates.
    Returns a RedirectResponse if the user is not logged in.
    """
    if isinstance(current_user, RedirectResponse):
        return current_user

    user_roles = {role.name.value for role in current_user.roles}
    
    return {
        "request": request,
        "user": current_user,
        "user_roles": user_roles
    }