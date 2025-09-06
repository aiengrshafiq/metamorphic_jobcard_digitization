from pydantic import BaseModel
from datetime import date
from typing import List, Optional

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