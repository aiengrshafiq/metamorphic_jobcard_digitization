# scripts/seed_projects.py
import sys
from pathlib import Path

# Add the project root to the Python path to allow for app imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import Project

# --- Configuration ---
# Define the range of project numbers you want to create
PROJECT_PREFIX = "Meta -"
START_NUMBER = 7
END_NUMBER = 100
# ---------------------

def create_projects(db: Session):
    """
    Checks for and creates any missing projects in the defined range.
    """
    print(f"Seeding projects from {START_NUMBER} to {END_NUMBER}...")
    
    # Get all project names currently in the database for an efficient check
    existing_project_names = {name for (name,) in db.query(Project.name).all()}
    
    projects_created_count = 0
    
    # Loop through the desired range of numbers (inclusive)
    for i in range(START_NUMBER, END_NUMBER + 1):
        # Format the project name with leading zeros (e.g., 007, 008, 009, 010, ... 100)
        project_name = f"{PROJECT_PREFIX} {i:03d}"
        
        # If the project name is not in the set of existing names, create it
        if project_name not in existing_project_names:
            db_project = Project(name=project_name)
            db.add(db_project)
            print(f"  -> Creating project: {project_name}")
            projects_created_count += 1
        else:
            print(f"  -> Project '{project_name}' already exists. Skipping.")
            
    if projects_created_count > 0:
        db.commit()
        print(f"\nSuccessfully created {projects_created_count} new project(s).")
    else:
        print("\nNo new projects needed. Database is up to date.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        create_projects(db)
    finally:
        db.close()