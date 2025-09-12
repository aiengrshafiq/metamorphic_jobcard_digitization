from pydantic import BaseModel, EmailStr
from datetime import date
from typing import List, Optional

from .models import UserRole # Import the enum

class TaskBase(BaseModel):
    task_details: Optional[str] = None
    quantity: Optional[float] = None
    units: Optional[str] = None
    priority: Optional[int] = 3
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    assigned_crew: Optional[str] = None

class TaskCreate(TaskBase):
    pass

class JobCardBase(BaseModel):
    project_name: str
    date_issued: date
    site_location: str
    site_engineer: str
    supervisor: str
    foreman: str

class JobCardCreate(JobCardBase):
    tasks: List[TaskCreate]

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class UserCreate(UserBase):
    name: str
    password: str
    roles: List[UserRole]

class User(UserBase):
    id: int
    is_active: bool
    roles: List[str] # Show role names as strings

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None