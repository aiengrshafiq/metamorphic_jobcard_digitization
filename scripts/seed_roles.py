# scripts/seed_roles.py
import sys
from pathlib import Path

# Add the project root to the Python path to allow for app imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import Role, UserRole

def create_all_roles(db: Session):
    """
    Checks for and creates any missing roles from the UserRole enum.
    """
    print("Seeding roles into the database...")
    
    # Get all role names currently in the database
    existing_roles = {role.name for role in db.query(Role).all()}
    
    roles_created_count = 0
    
    # Iterate through the UserRole enum
    for role_enum_member in UserRole:
        # If the role from the enum is not in the set of existing roles
        if role_enum_member not in existing_roles:
            db_role = Role(name=role_enum_member)
            db.add(db_role)
            print(f"  -> Creating role: {role_enum_member.value}")
            roles_created_count += 1
        else:
            print(f"  -> Role '{role_enum_member.value}' already exists. Skipping.")
            
    if roles_created_count > 0:
        db.commit()
        print(f"\nSuccessfully created {roles_created_count} new role(s).")
    else:
        print("\nNo new roles needed. Database is up to date.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        create_all_roles(db)
    finally:
        db.close()