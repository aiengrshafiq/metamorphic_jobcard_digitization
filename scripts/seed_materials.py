# scripts/seed_materials.py
import sys
import csv
from pathlib import Path

# Add the project root to the Python path to allow for app imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import Material

# The name of your CSV file
CSV_FILE_NAME = "Items_with_Units.xlsx - Sheet1.csv"

def seed_materials(db: Session):
    """
    Reads materials from a CSV file and inserts new materials into the database,
    skipping any that already exist by name.
    """
    print(f"Starting to seed materials from '{CSV_FILE_NAME}'...")
    
    csv_file_path = Path(__file__).parent / CSV_FILE_NAME
    if not csv_file_path.exists():
        print(f"Error: Could not find the file '{CSV_FILE_NAME}'.")
        print("Please make sure it is in the 'scripts' folder.")
        return

    # Fetch all existing material names once for efficient checking
    try:
        existing_names = {name for (name,) in db.query(Material.name).all()}
        print(f"Found {len(existing_names)} existing materials in the database.")
    except Exception as e:
        print(f"Error connecting to the database or querying materials: {e}")
        return

    materials_to_add = []
    
    with open(csv_file_path, mode='r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        next(reader)  # Skip the header row

        for row in reader:
            if not row or len(row) < 2:
                continue

            name = row[0].strip()
            unit = row[1].strip()

            # Skip if name is empty, has no unit, or already exists
            if not name or not unit or name in existing_names:
                print(f"  -> Skipping '{name}' (already exists or is invalid).")
                continue
            
            materials_to_add.append(
                Material(name=name, unit=unit)
            )
            # Add to set to prevent duplicates from within the CSV file itself
            existing_names.add(name)
            print(f"  -> Preparing to add: {name} ({unit})")

    if materials_to_add:
        print(f"\nAdding {len(materials_to_add)} new materials to the database...")
        db.add_all(materials_to_add)
        db.commit()
        print("Successfully committed new materials.")
    else:
        print("\nNo new materials to add. Database is up to date.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_materials(db)
    finally:
        db.close()
    print("Script finished.")