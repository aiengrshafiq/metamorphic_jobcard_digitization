# app/api/endpoints/pages.py
from fastapi import APIRouter, Depends, Request # <--- MAKE SURE 'Request' IS IMPORTED
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload, selectinload
import yaml
from pathlib import Path
import os
from sqlalchemy import or_

from app.api import deps
from app import models
from app.utils import generate_job_card_number

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- Safe Configuration Loading ---
def _load_config() -> dict:
    path = Path(os.getenv("APP_CONFIG_PATH", "config.yaml"))
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Warning: Config file at {path} not found.")
        return {}
app_config = _load_config()
# --- End Config Loading ---

# --- Protected Page Routes (Using the new dependency) ---

@router.get("/", response_class=HTMLResponse, tags=["Pages"])
async def dashboard(context: dict = Depends(deps.get_template_context)):
    if isinstance(context, RedirectResponse):
        return context
    
    context["page_title"] = "Dashboard"
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/job-card-form", response_class=HTMLResponse, tags=["Pages"])
async def read_job_card_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context

    # --- MODIFIED QUERIES ---
    # Fetch USERS with the role 'Site Engineer' instead of the old SiteEngineer table
    site_engineers = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SITE_ENGINEER).all()
    supervisors = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SUPERVISOR).all()
    foremen = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.FOREMAN).all()
    # ------------------------

    context.update({
        "page_title": "Metamorphic • Job Card (Assignment)",
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "site_engineers": site_engineers,
        "supervisors": supervisors,
        "foremen": foremen,
        "site_locations": app_config.get('site_locations', []),
        "units": app_config.get('units', []),
        "assigned_crew_options": app_config.get('assigned_crew_options', []),
        "initial_job_card_no": generate_job_card_number(db, app_config.get('site_locations', [''])[0])
    })
    return templates.TemplateResponse("form_a.html", context)


@router.get("/duty-officer-form", response_class=HTMLResponse, tags=["Pages"])
async def read_duty_officer_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
        
    # --- V3 DATA FILTERING LOGIC ---
    # Base query for Job Cards
    job_cards_query = db.query(models.JobCard).options(joinedload(models.JobCard.project))

    # Check if the user is privileged (can see everything)
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    is_privileged = bool(privileged_roles.intersection(context["user_roles"]))

    # If the user is NOT privileged, filter the job cards query
    if not is_privileged:
        current_user_id = context["user"].id
        job_cards_query = job_cards_query.filter(
            # A foreman should only see job cards they are assigned to
            models.JobCard.foreman_user_id == current_user_id
        )
    
    # Execute the final query
    job_cards = job_cards_query.order_by(models.JobCard.id.desc()).all()

    # Fetch USERS with the role 'Foreman/Duty Officer' for the signature dropdown
    foremen = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.FOREMAN).all()
    # ------------------------------------

    context.update({
        "page_title": "Metamorphic • Duty Officer Progress",
        "job_cards": job_cards, # Pass the potentially filtered list
        "foremen": foremen,     # Pass the list of users
        "equipment_conditions": app_config.get('equipment_conditions', []),
        "sub_contractor_coordinations": app_config.get('sub_contractor_coordinations', []),
        "delivery_statuses": app_config.get('delivery_statuses', []),
        "sop_statuses": app_config.get('sop_statuses', []),
    })
    return templates.TemplateResponse("form_b.html", context)


@router.get("/site-officer-form", response_class=HTMLResponse, tags=["Pages"])
async def read_site_officer_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
        
    # --- V3 DATA FILTERING LOGIC ---
    job_cards_query = db.query(models.JobCard).options(joinedload(models.JobCard.project))

    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    is_privileged = bool(privileged_roles.intersection(context["user_roles"]))

    # If the user is NOT privileged, filter the job cards to only show their own
    if not is_privileged:
        current_user_id = context["user"].id
        job_cards_query = job_cards_query.filter(
            # A supervisor should only see job cards they are assigned to
            models.JobCard.supervisor_user_id == current_user_id
        )
    
    job_cards = job_cards_query.order_by(models.JobCard.id.desc()).all()

    # Fetch USERS for the dropdowns based on their roles
    supervisors = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SUPERVISOR).all()
    foremen = db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.FOREMAN).all()
    # ------------------------------------

    context.update({
        "page_title": "Metamorphic • Sites Officers Daily Progress Report",
        "site_locations": app_config.get('site_locations', []),
        "supervisors": supervisors, # Pass the list of supervisor users
        "foremen": foremen,         # Pass the list of foreman users
        "job_cards": job_cards,     # Pass the filtered list of job cards
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "subcontractor_coordination_c": app_config.get('subcontractor_coordination_c', []),
        "site_condition_options": app_config.get('site_condition_options', []),
        "overall_site_health_options": app_config.get('overall_site_health_options', []),
        "yes_no_help_options": app_config.get('yes_no_help_options', []),
    })
    return templates.TemplateResponse("form_c.html", context)


@router.get("/job-card-tracking", response_class=HTMLResponse, tags=["Pages"])
async def job_card_tracking(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
    
    # Base query
    query = db.query(models.JobCard).options(
        joinedload(models.JobCard.project), 
        selectinload(models.JobCard.tasks)
    )

    # Check if the user is privileged (can see everything)
    privileged_roles = {'Super Admin', 'Admin', 'Operation Mananger', 'Project Manager'}
    is_privileged = bool(privileged_roles.intersection(context["user_roles"]))

    # If the user is NOT privileged, filter the query
    if not is_privileged:
        current_user_id = context["user"].id
        query = query.filter(
            or_(
                models.JobCard.site_engineer_user_id == current_user_id,
                models.JobCard.supervisor_user_id == current_user_id,
                models.JobCard.foreman_user_id == current_user_id
            )
        )
    
    job_cards = query.order_by(models.JobCard.id.desc()).all()
    
    context.update({
        "page_title": "My Job Cards", # Renamed for clarity
        "job_cards": job_cards,
        "task_statuses": app_config.get('task_statuses', [])
    })
    return templates.TemplateResponse("job_card_tracking.html", context)


@router.get("/material-requisition-form", response_class=HTMLResponse, tags=["Pages"])
async def read_material_requisition_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context
        
    context.update({
        "page_title": "Material Requisition Form",
        "projects": db.query(models.Project).order_by(models.Project.name).all(),
        "supervisors": db.query(models.User).join(models.User.roles).filter(models.Role.name == models.UserRole.SUPERVISOR).all(),
        "material_types": app_config.get('material_types', []),
        "urgency_levels": app_config.get('urgency_levels', []),
    })
    
    return templates.TemplateResponse("material_requisition_form.html", context)


@router.get("/approvals", response_class=HTMLResponse, tags=["Pages"])
async def approvals_page(context: dict = Depends(deps.get_template_context)):
    if isinstance(context, RedirectResponse):
        return context
        
    context["page_title"] = "My Approvals"
    return templates.TemplateResponse("approvals.html", context)


# --- Public Page Routes (No login required) ---

@router.get("/login", response_class=HTMLResponse, tags=["Pages"])
async def login_page(request: Request): # <--- CORRECTED: Was 'dict', now 'Request'
    """Serves the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse, tags=["Pages"])
async def register_page(request: Request, db: Session = Depends(deps.get_db)): # <--- CORRECTED: Was 'dict', now 'Request'
    """Serves the user registration page and provides a list of roles."""
    available_roles = db.query(models.Role).filter(models.Role.name != 'Super Admin').all()
    return templates.TemplateResponse(
        "register.html", 
        {"request": request, "roles": available_roles}
    )

@router.get("/nanny-log-form", response_class=HTMLResponse, tags=["Pages"])
async def nanny_log_form(
    context: dict = Depends(deps.get_template_context),
    db: Session = Depends(deps.get_db)
):
    if isinstance(context, RedirectResponse):
        return context

    # Fetch all users to populate the "Nanny Name" dropdown.
    # You could filter this by a 'Nanny' role in the future if you add one.
    all_users = db.query(models.User).filter(models.User.is_active == True).filter(models.Role.name == models.UserRole.User).order_by(models.User.name).all()
        
    context.update({
        "page_title": "Daily Nanny Log",
        "nannies": all_users,
    })
    return templates.TemplateResponse("nanny_log.html", context)