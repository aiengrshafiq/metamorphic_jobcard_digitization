# scripts/create_superuser.py
import asyncio
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Add the project root to the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, engine
from app.models import User, Role, UserRole, Base
from app.auth.security import get_password_hash

# --- Configuration ---
SUPERUSER_EMAIL = "shafiq@metamorphic.ae"
SUPERUSER_PASSWORD = "123456789"
# ---------------------

def create_roles(db: Session):
    """Creates all roles from the UserRole enum if they don't exist."""
    print("Checking and creating roles...")
    for role_name in UserRole:
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            db_role = Role(name=role_name)
            db.add(db_role)
            print(f"Created role: {role_name.value}")
    db.commit()
    print("Roles check complete.")

def create_superuser(db: Session):
    """Creates the superuser."""
    print("Attempting to create superuser...")
    
    # First, ensure all roles exist
    create_roles(db)

    # Check if the user already exists
    user = db.query(User).filter(User.email == SUPERUSER_EMAIL).first()
    if user:
        print(f"User with email '{SUPERUSER_EMAIL}' already exists. Aborting.")
        return

    # Get the Super Admin role
    super_admin_role = db.query(Role).filter(Role.name == UserRole.SUPER_ADMIN).first()
    if not super_admin_role:
        print("Super Admin role not found. Please ensure roles are created correctly.")
        return

    # Create the new user
    hashed_password = get_password_hash(SUPERUSER_PASSWORD)
    db_user = User(
        email=SUPERUSER_EMAIL,
        hashed_password=hashed_password,
        is_active=True,
        roles=[super_admin_role]  # Assign the role
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    print(f"Successfully created superuser '{SUPERUSER_EMAIL}'")

if __name__ == "__main__":
    print("Running initial setup script...")
    db = SessionLocal()
    try:
        # Create all tables if they don't exist (useful for first run)
        Base.metadata.create_all(bind=engine)
        create_superuser(db)
    finally:
        db.close()
    print("Script finished.")