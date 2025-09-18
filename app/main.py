# app/main.py
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqladmin import Admin

from app.core.database import engine
from app.core.config import settings
from app.admin import MyAuthBackend, create_admin_views

# Import all the routers
from app.api.endpoints import pages, job_cards, reports, procurement, uploads, users, approvals, nanny_log
from app.auth.router import router as auth_router



app = FastAPI(title="Metamorphic Job Card App V2")

# --- Setup Admin Panel ---
# Note: Ensure SECRET_KEY is set in your .env file for session management
authentication_backend = MyAuthBackend(secret_key=settings.SECRET_KEY)
admin = Admin(app, engine, authentication_backend=authentication_backend)
create_admin_views(admin)
# -------------------------

# --- Exception Handler and Middleware (from your old main.py) ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("\n--- DETAILED VALIDATION ERROR ---")
    print(json.dumps(exc.errors(), indent=4))
    print("--- END OF ERROR ---")
    error_messages = "; ".join([f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()])
    return JSONResponse(
        status_code=422,
        content={"message": f"Invalid form data. Please check the fields. Details: {error_messages}"}
    )

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "upgrade-insecure-requests"
    return response
# -----------------------------------------------------------------

# --- Include all API Routers ---
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(pages.router, tags=["Pages"]) # Root-level pages
app.include_router(job_cards.router, prefix="/job-cards", tags=["Job Cards"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(procurement.router, prefix="/procurement", tags=["Procurement"])
app.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["Approvals"])
app.include_router(nanny_log.router, prefix="/nanny-log", tags=["Nanny Log"])
# -------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}