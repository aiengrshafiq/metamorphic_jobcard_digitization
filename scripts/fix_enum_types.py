# scripts/fix_enum_types.py
import sys
from pathlib import Path
from sqlalchemy import text

# Add the project root to the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal

def drop_conflicting_types():
    """
    Connects to the database and drops the ENUM types that were
    partially created by a failed migration.
    """
    print("Connecting to the database to clean up conflicting types...")
    db = SessionLocal()
    try:
        # We drop these types. The CASCADE keyword handles any dependencies.
        # The next migration will recreate them correctly.
        types_to_drop = ["stagename", "commitmentpackage", "stagestatus"]
        
        for type_name in types_to_drop:
            try:
                print(f" -> Attempting to drop type '{type_name}'...")
                db.execute(text(f"DROP TYPE {type_name} CASCADE;"))
                print(f"    ... success.")
            except Exception as e:
                # It's okay if it fails, it might not exist.
                print(f"    ... info: could not drop type '{type_name}' (it may not exist).")
        
        db.commit()
        print("\nCleanup successful.")
    except Exception as e:
        db.rollback()
        print(f"\nAn error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    drop_conflicting_types()