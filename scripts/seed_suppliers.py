# scripts/seed_suppliers.py
import sys
import re
from pathlib import Path

# Add the project root to the Python path to allow for app imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import Supplier

# The raw data provided by the CEO
SUPPLIER_DATA = """
P V S GENERAL TRADING LLC	42518606	sales@pvsgroupuae.com
AL HAYER BUILDING MATERIALS TRADING LLC	97142892825	ahbmt76@gmail.com
RIKA TRADING LLC	+971 55 2237319	salerika9@gmail.com
PUMAN BUILDING MATERIAL TRADING LLC	971 50 5670015	pumandxb@emirates.net.ae
NILE BUILDING MATERIAL TRADING LLC	971 50 7861887	niletrdg@emirates.net.ae
DUCON INDUSTRIES FZCO	+971 4 8806996	sales@duconind.com
EMCON LLC	552710347	infouae@emcongcc.com
DOMUS CEMENT PRODUCTS INDUSTRIES LLC	25509517	info@domusblocks.com
ALSERKAL & ASSARAIN CONCRETE PRODUCTS	+971 50 424 8355	se.ac@alserkal-assarain.com
TRANSGULF CEMENT PRODUCTS LLC		
EMIRATES SPECIALISTS CO. LLC	04 3470767	dubai@esco.ae
QCON QUALITY CONSTRUCTION & HOME SOLUTIONS	+971 4 334881	
LAPIZ BLUE GENERAL TRADING LLC	+971 4 885 5257	info@lapizblue.com
LATICRETE MIDDLE EAST LLC	504329801	hemant@laticrete.me
SADATH BUILDING & CONSTRUCTION MATERIAL TRADING LLC	507702147	hunterpool_ali@yahoo.com
HIRA TRADING CO LLC / GEMAS MEA FZCO	547711383	
ATLANTIC POOLS & FOUNTAINS LLC	055-3365922	vikram@atecpoolme.com
HENGBO INDUSTRY AND TRADE FZCO	528012844	hengbo@zjhb.com
CHANG HE BUILDING MATERIAL TRADING -FZE	052-1928882	573110570@qq.com
ARABUILD	04 380 9555	showroom@arabuild.ae
AL MINTADHAR BUILDING TR. LLC	+971 56 695 5675	
ZERAMICO BUILDING & CONSTRUCTION MATERIAL TRADING CO LLC	04-2844335	info@zeramicotrading.com
AL FURAAT MARBLE AND GRANITE TRD.	586457502	
MAK POOLS & GARDENS LLC	+971 55 404 9299	sales@makpools.com
LOVE GARDEN LLC		love.gardens.dxb@gmail.com
ZAREI BUILDING MATERIALS TRADING LLC	050-9563643	
NAJMAT AL TAJ GLASS & ALUMINUM INSTALLATION & MAINTENANCE CO	553000453	najmataltajglass@gmail.com
JUGAL KISHOR FLOOR & WALL TILING WORK LLC	558372780	
MOHD. GULAM SHAFEEQ HEAVYEQUIPMENT TRANSPORT LLC,/ JAVED IQBAL	050-4933683	javid_iqbal135@yahoo.com
SHABBIR HUSSAIN	553779003	
STALLION ON DMAND LABOUR SUPPLY LLC	43420822	
AL HAYAT ELECT. SWITCHGEAR IND LLC	565475033	stany@alhayatswitchgear.com
ZAHRAT AL NAJAH INTERIOR DECORATION LLC	45759906	info@zahratalnajah.com
GEOSPATIAL TECHNICAL SERVICES LLC	50578868	
SUN WORLD BUILDING MATERIALS TRADING LLC	04 3536209	info@sunworldbmt.com
DUKE STEEL TRADING CO LLC	ISHWAR 055-1063365	salesdubai2@duke.ae
AL WAFA STEEL PRODUCTS MANUFACTURING LLC	+971 50 657 1204	alwafa7@emirates.net.ae
KMR GENERAL TRADING FZE LLC	050 198 7702	kmrtrading22@gmail.com
CEMEX TOPMIX LLC	052-4395106	
TEAM VENTURE GENERAL TRANSPORTATION	555687702	teamventure@mail.com
AVV GENERAL TRADING LLC 	528076123	
SULTAN INSULATION	+971 55 220 1696	
GLOBAL LIGHT & POWER LLC	+971 4 340 4458	
ATLANTIC POOLS	+971 52 870 1689	accounts@atecpoolme.com
CHINAREN ARTICLEFZCO / MOHAMMED HABIBUR RAHMAN	524075368	chinarenflooring@gmail.com
"""

def clean_phone(phone_str: str) -> str | None:
    """Removes non-digit characters to standardize phone numbers."""
    if not phone_str or not phone_str.strip():
        return None
    # Keep only numbers
    return re.sub(r'\D', '', phone_str.strip())

def clean_email(email_str: str) -> str | None:
    """Removes whitespace and ensures email contains '@'."""
    if not email_str or not email_str.strip() or '@' not in email_str:
        return None
    return email_str.strip()

def seed_suppliers(db: Session):
    """
    Parses the raw supplier data and inserts new suppliers into the database,
    skipping any that already exist by name.
    """
    print("Starting to seed supplier data...")
    
    # Fetch all existing supplier names once for efficient checking
    existing_names = {name for (name,) in db.query(Supplier.name).all()}
    print(f"Found {len(existing_names)} existing suppliers in the database.")
    
    suppliers_to_add = []
    
    # Process each line from the raw data
    for line in SUPPLIER_DATA.strip().split('\n'):
        if not line.strip():
            continue
        
        parts = line.split('\t')
        
        # Clean and assign parts safely
        name = parts[0].strip() if parts[0] else None
        phone = clean_phone(parts[1]) if len(parts) > 1 else None
        email = clean_email(parts[2]) if len(parts) > 2 else None
        
        # Skip if name is empty or already exists
        if not name or name in existing_names:
            print(f"  -> Skipping '{name}' (already exists or is empty).")
            continue
            
        # Add to our list to be created
        suppliers_to_add.append(
            Supplier(name=name, phone=phone, email=email)
        )
        # Add to existing_names set to prevent duplicates within this run
        existing_names.add(name)
        print(f"  -> Preparing to add: {name}")

    if suppliers_to_add:
        print(f"\nAdding {len(suppliers_to_add)} new suppliers to the database...")
        db.add_all(suppliers_to_add)
        db.commit()
        print("Successfully committed new suppliers.")
    else:
        print("\nNo new suppliers to add. Database is up to date.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_suppliers(db)
    finally:
        db.close()
    print("Script finished.")