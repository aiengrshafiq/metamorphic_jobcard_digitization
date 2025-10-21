from pydantic import BaseModel, EmailStr,ConfigDict
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


class NannyLogCreate(BaseModel):
    log_date: date
    nanny_id: int
    handwashing_checks: Optional[List[str]] = []
    environment_checks: Optional[List[str]] = []
    breakfast_details: Optional[str] = None
    breakfast_amount: Optional[str] = None
    lunch_details: Optional[str] = None
    lunch_amount: Optional[str] = None
    snack_details: Optional[str] = None
    snack_amount: Optional[str] = None
    dinner_details: Optional[str] = None
    dinner_amount: Optional[str] = None
    hydration_morning_cups: Optional[str] = None
    hydration_afternoon_cups: Optional[str] = None
    hydration_evening_cups: Optional[str] = None
    restricted_foods_given: bool = False
    restricted_foods_details: Optional[str] = None
    nap_duration_minutes: Optional[int] = None
    bedtime_by_830pm: bool = False
    total_sleep_hours: Optional[str] = None
    outdoor_play_completed: bool = False
    outdoor_play_minutes: Optional[int] = None
    screen_time_minutes: Optional[int] = None
    temperature_celsius: Optional[float] = None
    appetite: Optional[str] = None
    behavior: Optional[str] = None
    signs_of_illness: Optional[str] = None
    nanny_notes: Optional[str] = None




# --- Base Schemas for nesting ---
# These are simple versions of your models for API responses

class ProjectSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

class SupplierSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

# --- Schemas for Report Items ---

class JobCardSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_card_no: str
    project: ProjectSchema
    supervisor_user: Optional[UserSchema] = None
    date_issued: date
    status: str

class MaterialRequisitionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mr_number: str
    project: ProjectSchema
    requested_by: UserSchema
    request_date: date
    status: str
    mr_approval: Optional[str]
    pm_approval: Optional[str]
    qs_approval: Optional[str]

class LPOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    lpo_number: str
    project: ProjectSchema
    supplier: SupplierSchema
    lpo_date: date
    status: str
    grand_total: float