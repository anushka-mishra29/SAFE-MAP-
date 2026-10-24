from .database import SessionLocal
from .models import Location, Report, SafePlace


def seed_demo_data():
    db = SessionLocal()
    try:
        if db.query(Location).count() == 0:
            # Clearly named synthetic coordinates for demonstration only.
            db.add_all([
                Location(latitude=26.9124, longitude=75.7873, area_name="Central Demo Zone", lighting_score=92, crowd_level=88, calculated_safety_score=88, is_demo=True),
                Location(latitude=26.9157, longitude=75.8000, area_name="Moderate Demo Zone", lighting_score=68, crowd_level=62, calculated_safety_score=67, is_demo=True),
                Location(latitude=26.9055, longitude=75.7950, area_name="Caution Demo Zone", lighting_score=42, crowd_level=35, calculated_safety_score=43, is_demo=True),
                Location(latitude=26.9200, longitude=75.8100, area_name="Campus Demo Zone", lighting_score=84, crowd_level=78, calculated_safety_score=81, is_demo=True),
            ])
        if db.query(SafePlace).count() == 0:
            db.add_all([
                SafePlace(name="Demo Police Station", place_type="police_station", latitude=26.9147, longitude=75.7922, is_demo=True),
                SafePlace(name="Demo City Hospital", place_type="hospital", latitude=26.9092, longitude=75.8014, is_demo=True),
                SafePlace(name="SafeMap Demo Safe Booth", place_type="shelter", latitude=26.9185, longitude=75.8040, is_demo=True),
                SafePlace(name="Demo Pharmacy", place_type="pharmacy", latitude=26.9077, longitude=75.7895, contact_number="", is_demo=True),
            ])
        if db.query(Report).count() == 0:
            db.add(Report(title="Demo road hazard", latitude=26.9124, longitude=75.7873, incident_type="Road Hazard",
                          description="Demonstration-only sample report; not a verified incident.",
                          severity=2, status="Demo sample (unverified)", is_demo=True))
        db.commit()
    finally:
        db.close()
