# app/api/endpoints/pages.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload, selectinload
import yaml
from pathlib import Path
import os

from app.api import deps
from app import models
from app.utils import generate_job_card_number


# Add RedirectResponse here
from fastapi.responses import HTMLResponse, RedirectResponse


router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- Safe Configuration Loading ---
def _load_config() -> dict:
    # Use an absolute path inside the container
    #path = Path(os.getenv("APP_CONFIG_PATH", "/app/config.yaml"))
    path = Path(os.getenv("APP_CONFIG_PATH", "config.yaml"))
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Warning: Config file at {path} not found.")
        return {}
app_config = _load_config()
# --- End Config Loading ---


# @router.get("/", response_class=HTMLResponse, tags=["Pages"])
# async def dashboard(request: Request):
#     return templates.TemplateResponse("dashboard.html", {"request": request, "page_title": "Dashboard"})

# NEW protected version:
@router.get("/", response_class=HTMLResponse, tags=["Pages"])
async def dashboard(request: Request, current_user: models.User = Depends(deps.get_current_user_from_cookie)):
    if isinstance(current_user, RedirectResponse):
        return current_user # If dependency returns a redirect, execute it
    
    # If it's a valid user, render the page and pass the user object
    return templates.TemplateResponse(
        "dashboard.html", 
        {"request": request, "page_title": "Dashboard", "user": current_user}
    )

@router.get("/job-card-form", response_class=HTMLResponse, tags=["Pages"])
async def read_job_card_form(request: Request, db: Session = Depends(deps.get_db)):
    context = {
        "request": request,
        "page_title": "Metamorphic • Job Card (Assignment)",
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "site_engineers": db.query(models.SiteEngineer).order_by(models.SiteEngineer.name).all(),
        "supervisors": db.query(models.Supervisor).order_by(models.Supervisor.name).all(),
        "foremen": db.query(models.Foreman).order_by(models.Foreman.name).all(),
        "site_locations": app_config.get('site_locations', []),
        "units": app_config.get('units', []),
        "assigned_crew_options": app_config.get('assigned_crew_options', []),
        "initial_job_card_no": generate_job_card_number(db, app_config.get('site_locations', [''])[0])
    }
    return templates.TemplateResponse("form_a.html", context)

@router.get("/duty-officer-form", response_class=HTMLResponse, tags=["Pages"])
async def read_duty_officer_form(request: Request, db: Session = Depends(deps.get_db)):
    context = {
        "request": request,
        "page_title": "Metamorphic • Duty Officer Progress",
        "job_cards": db.query(models.JobCard).options(joinedload(models.JobCard.project)).order_by(models.JobCard.id.desc()).all(),
        "foremen": db.query(models.Foreman).order_by(models.Foreman.name).all(),
        "equipment_conditions": app_config.get('equipment_conditions', []),
        "sub_contractor_coordinations": app_config.get('sub_contractor_coordinations', []),
        "delivery_statuses": app_config.get('delivery_statuses', []),
        "sop_statuses": app_config.get('sop_statuses', []),
    }
    return templates.TemplateResponse("form_b.html", context)

@router.get("/site-officer-form", response_class=HTMLResponse, tags=["Pages"])
async def read_site_officer_form(request: Request, db: Session = Depends(deps.get_db)):
    context = {
        "request": request,
        "page_title": "Metamorphic • Sites Officers Daily Progress Report",
        "site_locations": app_config.get('site_locations', []),
        "supervisors": db.query(models.Supervisor).order_by(models.Supervisor.name).all(),
        "foremen": db.query(models.Foreman).order_by(models.Foreman.name).all(),
        "job_cards": db.query(models.JobCard).options(joinedload(models.JobCard.project)).order_by(models.JobCard.id.desc()).all(),
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "subcontractor_coordination_c": app_config.get('subcontractor_coordination_c', []),
        "site_condition_options": app_config.get('site_condition_options', []),
        "overall_site_health_options": app_config.get('overall_site_health_options', []),
        "yes_no_help_options": app_config.get('yes_no_help_options', []),
    }
    return templates.TemplateResponse("form_c.html", context)

@router.get("/job-card-tracking", response_class=HTMLResponse, tags=["Pages"])
async def job_card_tracking(request: Request, db: Session = Depends(deps.get_db)):
    job_cards = db.query(models.JobCard).options(joinedload(models.JobCard.project), selectinload(models.JobCard.tasks)).order_by(models.JobCard.id.desc()).all()
    context = {
        "request": request,
        "page_title": "Job Card Tracking",
        "job_cards": job_cards,
        "task_statuses": app_config.get('task_statuses', [])
    }
    return templates.TemplateResponse("job_card_tracking.html", context)

@router.get("/material-requisition-form", response_class=HTMLResponse, tags=["Pages"])
async def read_material_requisition_form(request: Request, db: Session = Depends(deps.get_db)):
    context = {
        "request": request,
        "page_title": "Material Requisition Form",
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "supervisors": db.query(models.Supervisor).order_by(models.Supervisor.name).all(),
        "material_types": app_config.get('material_types', []),
        "urgency_levels": app_config.get('urgency_levels', []),
    }
    return templates.TemplateResponse("material_requisition_form.html", context)


@router.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request):
    """Serves the login page."""
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/register", response_class=HTMLResponse, tags=["Pages"])
async def register_page(request: Request, db: Session = Depends(deps.get_db)):
    """Serves the user registration page and provides a list of roles."""
    # Fetch all roles except Super Admin, which shouldn't be assignable from a public form
    available_roles = db.query(models.Role).filter(models.Role.name != 'Super Admin').all()
    return templates.TemplateResponse(
        "register.html", 
        {"request": request, "roles": available_roles}
    )